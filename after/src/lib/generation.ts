import crypto from "node:crypto";
import { getStore, type Generation, type Session } from "@/lib/store";
import { getProvider } from "@/lib/providers";
import { POLICY } from "@/lib/config";
import { HttpError } from "@/lib/session";
import { applyWatermark } from "@/lib/image/watermark";
import { fetchImageBuffer } from "@/lib/image/normalize";
import { buildSurgeryPrompt, describeSelection, INTENSITIES, INTENSITY_LABELS, SURGERY_PARTS, type Intensity, type SurgerySelection } from "../../prompts/surgery";
import type { ImageEditProvider, JobStatus } from "@/lib/providers";
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

/**
 * 여러 프롬프트를 한 생성으로 묶을 때(강도 3단계 비교) 외부 작업 ID 를 "|" 로 이어 붙인다.
 * 프로바이더 내부의 "," 구분(장수 분할)과 겹치지 않는다.
 */
const MULTI_SEP = "|";

async function multiStatus(provider: ImageEditProvider, jobId: string): Promise<JobStatus> {
  const ids = jobId.split(MULTI_SEP);
  const all = await Promise.all(ids.map((id) => provider.status(id)));
  const failed = all.find((s) => s.state === "failed");
  if (failed) return failed;
  if (all.every((s) => s.state === "done")) return { state: "done" };
  if (all.some((s) => s.state === "running")) return { state: "running" };
  return { state: "queued", queuePosition: all.find((s) => s.queuePosition !== undefined)?.queuePosition };
}

async function multiResult(provider: ImageEditProvider, jobId: string) {
  const ids = jobId.split(MULTI_SEP);
  const all = await Promise.all(ids.map((id) => provider.result(id)));
  return { images: all.flatMap((r) => r.images), seed: all[0]?.seed };
}

/** 켜진 부위를 전부 같은 강도로 맞춘 선택값 (강도 비교용) */
export function selectionAtIntensity(selection: SurgerySelection, intensity: Intensity): SurgerySelection {
  const out = {} as SurgerySelection;
  for (const p of SURGERY_PARTS) out[p] = { enabled: selection[p].enabled, intensity: selection[p].enabled ? intensity : selection[p].intensity };
  return out;
}

/** 얼굴 생성물의 "선택된" 결과 인덱스 (비교 모드에서 사용자가 고른 강도, 기본은 중간/첫 번째) */
export function chosenIndex(gen: Generation): number {
  const n = gen.outputPaths.length;
  if (n === 0) return 0;
  const c = gen.params.chosen;
  if (typeof c === "number" && c >= 0 && c < n) return c;
  return n === 3 ? 1 : 0;
}

export type FaceOptions = { compare: boolean };

export async function startFaceGeneration(session: Session, selection: SurgerySelection, opts: FaceOptions = { compare: true }): Promise<Generation> {
  const store = await getStore();
  if (!session.currentUploadId) throw new HttpError(400, "먼저 정면 사진을 올려 주세요.");
  const front = await store.getUpload(session.currentUploadId);
  if (!front) throw new HttpError(400, "사진이 만료됐어요. 다시 올려 주세요.");

  await guardRateLimit(session.id);

  const ok = await store.consumeCredits(session.id, "face", 1);
  if (!ok) throw new HttpError(402, "무료 얼굴 생성 크레딧을 다 썼어요.", { paywall: true, kind: "face" });

  // 비교 모드: 켜진 부위를 약·중·강으로 각각 한 장씩. 한 번의 크레딧으로 3장.
  const variants: Intensity[] = opts.compare ? [...INTENSITIES] : [];
  const selections = opts.compare ? variants.map((i) => selectionAtIntensity(selection, i)) : [selection];
  const prompts = selections.map(buildSurgeryPrompt);
  const provider = getProvider("face");

  try {
    const imageUrl = await store.signedUrl("private", front.path, SIGNED_URL_TTL);
    const jobIds = await Promise.all(prompts.map((prompt) => provider.submit({ prompt, imageUrls: [imageUrl], numImages: 1 })));
    const gen = await store.createGeneration({
      sessionId: session.id,
      kind: "face",
      providerId: provider.id,
      externalJobId: jobIds.map((j) => j.jobId).join(MULTI_SEP),
      status: "queued",
      prompt: prompts.join("\n\n---\n\n"),
      params: {
        selection,
        label: describeSelection(selection),
        compare: opts.compare,
        variants, // ["low","mid","high"] 또는 []
        variantLabels: opts.compare ? variants.map((v) => INTENSITY_LABELS[v]) : [describeSelection(selection)],
        chosen: null,
      },
      inputUploadIds: [front.id],
      inputGenerationId: null,
      outputPaths: [],
      error: null,
      expiresAt: expiresAt(POLICY.generatedRetentionHours),
    });
    await store.updateSession(session.id, { currentFaceGenerationId: gen.id, currentPhotoGenerationId: null, selection });
    await store.logEvent({ sessionId: session.id, name: "face_started", props: { compare: opts.compare, label: describeSelection(selection) } });
    return gen;
  } catch (e) {
    await store.refundCredits(session.id, "face", 1);
    throw e;
  }
}

/** 비교 모드에서 사용자가 강도를 고른다. 인생샷과 공유는 이 인덱스를 쓴다. */
export async function chooseFaceVariant(session: Session, index: number): Promise<Generation> {
  const store = await getStore();
  if (!session.currentFaceGenerationId) throw new HttpError(400, "얼굴 생성 기록이 없어요.");
  const face = await store.getGeneration(session.currentFaceGenerationId);
  if (!face || face.status !== "done") throw new HttpError(400, "얼굴 생성이 아직 끝나지 않았어요.");
  if (index < 0 || index >= face.outputPaths.length) throw new HttpError(400, "잘못된 선택이에요.");
  await store.logEvent({ sessionId: session.id, name: "face_chosen", props: { index } });
  return store.updateGeneration(face.id, { params: { ...face.params, chosen: index } });
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
    const idx = chosenIndex(face);
    const refs: string[] = [store.publicUrl(face.outputPaths[idx])];
    // public 버킷 URL 은 워터마크가 있는 이미지다. 모델이 워터마크를 따라 그리지 않도록 워터마크 없는 얼굴을 임시 서명 URL 로 준다.
    const cleanPaths = Array.isArray(face.params.cleanPaths) ? (face.params.cleanPaths as string[]) : [];
    const cleanFacePath = cleanPaths[idx] ?? (face.params.cleanPath as string | undefined) ?? null;
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
    await store.logEvent({ sessionId: session.id, name: "photos_started", props: { place, mood } });
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

  let st: JobStatus;
  try {
    st = await multiStatus(provider, gen.externalJobId);
  } catch (e) {
    console.error("provider.status failed", e);
    return gen; // 일시적 오류. 다음 폴링에서 다시.
  }

  if (st.state === "failed") {
    await refundFor(gen);
    await store.logEvent({ sessionId: gen.sessionId, name: `${gen.kind}_failed`, props: { error: st.error ?? null } });
    return store.updateGeneration(gen.id, { status: "failed", error: st.error ?? "생성에 실패했어요." });
  }
  if (st.state === "queued") return gen.status === "queued" ? gen : store.updateGeneration(gen.id, { status: "queued" });
  if (st.state === "running") return gen.status === "running" ? gen : store.updateGeneration(gen.id, { status: "running" });

  // done → 결과 처리
  const claimed = await store.updateGeneration(gen.id, { status: "processing" });
  try {
    const result = await multiResult(provider, gen.externalJobId);
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
    await store.logEvent({ sessionId: gen.sessionId, name: gen.kind === "face" ? "face_done" : "photos_done", props: { count: outputPaths.length } });
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
    chosen: gen.status === "done" ? chosenIndex(gen) : null,
    createdAt: gen.createdAt,
  };
}
