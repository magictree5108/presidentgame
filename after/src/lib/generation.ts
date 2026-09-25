import crypto from "node:crypto";
import { getStore, type Generation, type Session } from "@/lib/store";
import { getProvider } from "@/lib/providers";
import { POLICY } from "@/lib/config";
import { HttpError } from "@/lib/session";
import { applyWatermark } from "@/lib/image/watermark";
import { fetchImageBuffer } from "@/lib/image/normalize";
import { buildSurgeryPrompt, describeSelection, type SurgerySelection } from "../../prompts/surgery";
import { buildLifeshotPrompt, PLACES, type MoodId, type PlaceId } from "../../prompts/lifeshot";

/**
 * 생성 서비스. 라우트 핸들러는 얇게 두고 로직은 여기 모은다.
 *
 * 흐름: 분당 제한 → 크레딧 차감 → 서명 URL 발급 → 프로바이더 submit → generations 행 생성
 * 폴링: refreshGeneration 이 프로바이더 상태를 보고, 끝났으면 결과를 내려받아 워터마크를 굽고 public 버킷에 저장한다.
 */

const SIGNED_URL_TTL = 60 * 20; // 외부 모델이 입력 이미지를 읽는 데 쓰는 서명 URL 수명

function expiresAt(hours: number) {
  return new Date(Date.now() + hours * 3600_000).toISOString();
}

async function guardRateLimit(sessionId: string) {
  const store = await getStore();
  const rl = await store.checkRateLimit(sessionId, "generate", POLICY.rateLimit.perMinute, POLICY.rateLimit.windowSeconds);
  if (!rl.allowed) {
    throw new HttpError(429, `요청이 너무 잦아요. ${rl.retryAfterSeconds}초 뒤에 다시 시도해 주세요.`, { retryAfter: rl.retryAfterSeconds });
  }
}

export async function startFaceGeneration(session: Session, selection: SurgerySelection): Promise<Generation> {
  const store = await getStore();
  if (!session.currentUploadId) throw new HttpError(400, "먼저 정면 사진을 올려 주세요.");
  const front = await store.getUpload(session.currentUploadId);
  if (!front) throw new HttpError(400, "사진이 만료됐어요. 다시 올려 주세요.");

  await guardRateLimit(session.id);

  const ok = await store.consumeCredits(session.id, "face", 1);
  if (!ok) throw new HttpError(402, "무료 얼굴 생성 크레딧을 다 썼어요.", { paywall: true, kind: "face" });

  const prompt = buildSurgeryPrompt(selection);
  const provider = getProvider("face");

  try {
    const imageUrl = await store.signedUrl("private", front.path, SIGNED_URL_TTL);
    const { jobId } = await provider.submit({ prompt, imageUrls: [imageUrl], numImages: 1 });
    const gen = await store.createGeneration({
      sessionId: session.id,
      kind: "face",
      providerId: provider.id,
      externalJobId: jobId,
      status: "queued",
      prompt,
      params: { selection, label: describeSelection(selection) },
      inputUploadIds: [front.id],
      inputGenerationId: null,
      outputPaths: [],
      error: null,
      expiresAt: expiresAt(POLICY.generatedRetentionHours),
    });
    await store.updateSession(session.id, { currentFaceGenerationId: gen.id, currentPhotoGenerationId: null, selection });
    return gen;
  } catch (e) {
    await store.refundCredits(session.id, "face", 1);
    throw e;
  }
}

export async function startPhotoGeneration(session: Session, place: PlaceId, mood: MoodId): Promise<Generation> {
  const store = await getStore();
  if (!session.currentFaceGenerationId) throw new HttpError(400, "먼저 성형 후 얼굴을 만들어 주세요.");
  const face = await store.getGeneration(session.currentFaceGenerationId);
  if (!face || face.status !== "done" || !face.outputPaths.length) throw new HttpError(400, "성형 후 얼굴이 아직 준비되지 않았어요.");

  await guardRateLimit(session.id);

  const n = POLICY.photosPerSet;
  const ok = await store.consumeCredits(session.id, "photo", n);
  if (!ok) throw new HttpError(402, "무료 인생샷 크레딧을 다 썼어요.", { paywall: true, kind: "photo" });

  const prompt = buildLifeshotPrompt(place, mood);
  const provider = getProvider("photo");

  try {
    // 레퍼런스 순서: 성형 후 얼굴(기준) → 원본 정면 → 원본 측면
    const uploads = await store.listUploads(session.id);
    const front = uploads.find((u) => u.id === session.currentUploadId) ?? uploads.find((u) => u.kind === "front");
    const sides = uploads.filter((u) => u.kind === "side");
    const refs: string[] = [store.publicUrl(face.outputPaths[0])];
    // public 버킷 URL 은 워터마크가 있는 이미지다. 모델이 워터마크를 따라 그리지 않도록 워터마크 없는 얼굴을 임시 서명 URL 로 준다.
    const cleanFacePath = (face.params.cleanPath as string | undefined) ?? null;
    if (cleanFacePath) refs[0] = await store.signedUrl("private", cleanFacePath, SIGNED_URL_TTL);
    if (front) refs.push(await store.signedUrl("private", front.path, SIGNED_URL_TTL));
    for (const s of sides) refs.push(await store.signedUrl("private", s.path, SIGNED_URL_TTL));

    const { jobId } = await provider.submit({ prompt, imageUrls: refs, numImages: n, aspectRatio: PLACES[place].aspectRatio });
    const gen = await store.createGeneration({
      sessionId: session.id,
      kind: "photo",
      providerId: provider.id,
      externalJobId: jobId,
      status: "queued",
      prompt,
      params: { place, mood },
      inputUploadIds: uploads.map((u) => u.id),
      inputGenerationId: face.id,
      outputPaths: [],
      error: null,
      expiresAt: expiresAt(POLICY.generatedRetentionHours),
    });
    await store.updateSession(session.id, { currentPhotoGenerationId: gen.id });
    return gen;
  } catch (e) {
    await store.refundCredits(session.id, "photo", n);
    throw e;
  }
}

/**
 * 폴링 한 번. 프로바이더 상태를 확인하고 끝났으면 결과를 처리한다.
 * 결과 처리(다운로드 → 워터마크 → 저장)는 한 번만 일어나야 하므로 status 를 processing 으로 먼저 바꾼다.
 */
export async function refreshGeneration(gen: Generation): Promise<Generation> {
  if (gen.status === "done" || gen.status === "failed" || gen.status === "processing") return gen;
  if (!gen.externalJobId) return gen;
  const store = await getStore();
  const provider = getProvider(gen.kind === "face" ? "face" : "photo");

  let st;
  try {
    st = await provider.status(gen.externalJobId);
  } catch (e) {
    console.error("provider.status failed", e);
    return gen; // 일시적 오류. 다음 폴링에서 다시.
  }

  if (st.state === "failed") {
    await refundFor(gen);
    return store.updateGeneration(gen.id, { status: "failed", error: st.error ?? "생성에 실패했어요." });
  }
  if (st.state === "queued") return gen.status === "queued" ? gen : store.updateGeneration(gen.id, { status: "queued" });
  if (st.state === "running") return gen.status === "running" ? gen : store.updateGeneration(gen.id, { status: "running" });

  // done → 결과 처리
  const claimed = await store.updateGeneration(gen.id, { status: "processing" });
  try {
    const result = await provider.result(gen.externalJobId);
    const outputPaths: string[] = [];
    const cleanPaths: string[] = [];
    for (let i = 0; i < result.images.length; i++) {
      const raw = await fetchImageBuffer(result.images[i].url);
      const id = crypto.randomUUID();
      // 워터마크 없는 사본은 private 버킷에만 둔다 (인생샷 레퍼런스, 공유 카드 합성용). 브라우저에는 절대 내려가지 않는다.
      const cleanPath = `${gen.sessionId}/clean/${id}.jpg`;
      await store.putBlob("private", cleanPath, raw, "image/jpeg");
      cleanPaths.push(cleanPath);
      // 브라우저와 공유 페이지가 보는 이미지는 전부 워터마크가 구워진 public 사본이다.
      const marked = await applyWatermark(raw);
      const path = `${gen.sessionId}/${gen.kind}/${id}.jpg`;
      await store.putBlob("public", path, marked, "image/jpeg");
      outputPaths.push(path);
    }
    return store.updateGeneration(gen.id, {
      status: "done",
      outputPaths,
      params: { ...claimed.params, cleanPath: cleanPaths[0], cleanPaths, seed: result.seed ?? null },
    });
  } catch (e) {
    console.error("result processing failed", e);
    await refundFor(gen);
    return store.updateGeneration(gen.id, { status: "failed", error: e instanceof Error ? e.message : "결과 처리에 실패했어요." });
  }
}

async function refundFor(gen: Generation) {
  const store = await getStore();
  if (gen.kind === "face") await store.refundCredits(gen.sessionId, "face", 1);
  else await store.refundCredits(gen.sessionId, "photo", POLICY.photosPerSet);
}

/** 클라이언트에 내려주는 형태. 경로 대신 URL 을 준다. */
export async function publicGeneration(gen: Generation) {
  const store = await getStore();
  return {
    id: gen.id,
    kind: gen.kind,
    status: gen.status,
    error: gen.error,
    params: { ...gen.params, cleanPath: undefined, cleanPaths: undefined },
    outputs: gen.outputPaths.map((p) => store.publicUrl(p)),
    createdAt: gen.createdAt,
  };
}
