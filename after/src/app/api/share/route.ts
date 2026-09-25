import { jsonError, requireSession, HttpError } from "@/lib/session";
import { getStore } from "@/lib/store";
import { privateGenerationPaths } from "@/lib/store/paths";
import { newShareId } from "@/lib/ids";
import { composeBeforeAfterStory, composeOg, composePhotoStory } from "@/lib/image/sharecard";
import { POLICY } from "@/lib/config";
import { appUrl } from "@/lib/brand";
import { describeSelection, type SurgerySelection } from "../../../../prompts/surgery";
import { MOODS, PLACES, type MoodId, type PlaceId } from "../../../../prompts/lifeshot";

/**
 * 공유 카드 생성. 현재 세션의 얼굴 생성 + 인생샷 생성으로
 *  - OG 이미지(public), 스토리 슬라이드 5장(private) 을 합성하고 shares 행을 만든다.
 * 같은 조합으로 이미 만든 공유가 있으면 그것을 돌려준다.
 */
export async function POST() {
  try {
    const session = await requireSession();
    const store = await getStore();
    if (!session.currentFaceGenerationId || !session.currentPhotoGenerationId) throw new HttpError(400, "얼굴과 인생샷을 먼저 만들어 주세요.");
    const [face, photos] = await Promise.all([
      store.getGeneration(session.currentFaceGenerationId),
      store.getGeneration(session.currentPhotoGenerationId),
    ]);
    if (!face || face.status !== "done" || !photos || photos.status !== "done") throw new HttpError(400, "생성이 아직 끝나지 않았어요.");

    const existing = (await store.listShares(session.id)).find(
      (s) => s.faceGenerationId === face.id && s.photoGenerationId === photos.id,
    );
    if (existing) return Response.json({ share: shareView(existing.id) });

    const front = session.currentUploadId ? await store.getUpload(session.currentUploadId) : null;
    // 합성에는 워터마크 없는 private 사본을 쓴다 (없으면 public 사본으로 대체). 결과물에는 마지막에 워터마크가 한 번 구워진다.
    const faceClean = privateGenerationPaths(face);
    const photoClean = privateGenerationPaths(photos);
    const readGen = async (cleanPath: string | undefined, publicPath: string) =>
      (cleanPath ? await store.getBlob("private", cleanPath) : null) ?? store.getBlob("public", publicPath);
    const [beforeBuf, afterBuf, ...photoBufs] = await Promise.all([
      front ? store.getBlob("private", front.path) : null,
      readGen(faceClean[0], face.outputPaths[0]),
      ...photos.outputPaths.map((p, i) => readGen(photoClean[i], p)),
    ]);
    if (!afterBuf) throw new HttpError(500, "얼굴 이미지를 읽지 못했어요.");
    const photoBuffers = photoBufs.filter((b): b is Buffer => !!b);

    const selection = (face.params.selection ?? session.selection) as SurgerySelection | null;
    const faceLabel = selection ? describeSelection(selection) : "";
    const place = photos.params.place as PlaceId;
    const mood = photos.params.mood as MoodId;
    const photoLabel = `${PLACES[place]?.label ?? ""} · ${MOODS[mood]?.label ?? ""}`;

    const id = newShareId();
    const ogPath = `${session.id}/share/${id}/og.jpg`;
    const og = await composeOg({ after: afterBuf, photos: photoBuffers, caption: photoLabel });
    await store.putBlob("public", ogPath, og, "image/jpeg");

    const storyPaths: string[] = [];
    if (beforeBuf) {
      const s1 = await composeBeforeAfterStory({ before: beforeBuf, after: afterBuf, caption: faceLabel });
      const p = `${session.id}/share/${id}/story-1.jpg`;
      await store.putBlob("private", p, s1, "image/jpeg");
      storyPaths.push(p);
    }
    for (let i = 0; i < photoBuffers.length; i++) {
      const s = await composePhotoStory({ photo: photoBuffers[i], caption: photoLabel, index: i + 1, total: photoBuffers.length });
      const p = `${session.id}/share/${id}/story-${storyPaths.length + 1}.jpg`;
      await store.putBlob("private", p, s, "image/jpeg");
      storyPaths.push(p);
    }

    await store.createShare({
      id,
      sessionId: session.id,
      faceGenerationId: face.id,
      photoGenerationId: photos.id,
      afterPath: face.outputPaths[0],
      photoPaths: photos.outputPaths,
      ogPath,
      storyPaths,
      caption: `${faceLabel} · ${photoLabel}`,
      expiresAt: new Date(Date.now() + POLICY.generatedRetentionHours * 3600_000).toISOString(),
    });
    return Response.json({ share: shareView(id) });
  } catch (e) {
    return jsonError(e);
  }
}

function shareView(id: string) {
  return { id, url: `${appUrl()}/s/${id}`, storyUrl: `/api/share/${id}/story` };
}
