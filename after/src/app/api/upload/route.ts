import crypto from "node:crypto";
import { jsonError, requireSession, HttpError } from "@/lib/session";
import { getStore } from "@/lib/store";
import { normalizeUpload } from "@/lib/image/normalize";
import { POLICY } from "@/lib/config";

/**
 * 사진 업로드. multipart/form-data: front(필수 1장), side(선택 최대 2장).
 * 이전 업로드와 그에 딸린 생성물은 새 업로드로 대체된다.
 */
export async function POST(req: Request) {
  try {
    const session = await requireSession();
    const form = await req.formData();
    const front = form.get("front");
    const sides = form.getAll("side").filter((f): f is File => f instanceof File && f.size > 0);
    if (!(front instanceof File) || front.size === 0) throw new HttpError(400, "정면 사진이 필요해요.");
    if (sides.length > POLICY.maxSidePhotos) throw new HttpError(400, `측면 사진은 최대 ${POLICY.maxSidePhotos}장이에요.`);
    for (const f of [front, ...sides]) {
      if (f.size > POLICY.uploadMaxBytes) throw new HttpError(413, "사진 용량이 너무 커요 (12MB 이하).");
      if (!f.type.startsWith("image/")) throw new HttpError(400, "이미지 파일만 올릴 수 있어요.");
    }

    const store = await getStore();
    // 이전 업로드 정리
    const old = await store.listUploads(session.id);
    if (old.length) {
      await store.deleteBlobs("private", old.map((u) => u.path));
      await store.deleteUploads(old.map((u) => u.id));
    }

    const expiresAt = new Date(Date.now() + POLICY.originalRetentionHours * 3600_000).toISOString();
    const saveOne = async (file: File, kind: "front" | "side") => {
      const { buffer, width, height } = await normalizeUpload(Buffer.from(await file.arrayBuffer()));
      const path = `${session.id}/uploads/${crypto.randomUUID()}.jpg`;
      await store.putBlob("private", path, buffer, "image/jpeg");
      return store.createUpload({ sessionId: session.id, kind, path, width, height, expiresAt });
    };

    const frontUp = await saveOne(front, "front");
    const sideUps = [];
    for (const s of sides) sideUps.push(await saveOne(s, "side"));

    await store.updateSession(session.id, {
      currentUploadId: frontUp.id,
      currentFaceGenerationId: null,
      currentPhotoGenerationId: null,
    });

    return Response.json({
      ok: true,
      uploads: [frontUp, ...sideUps].map((u) => ({ id: u.id, kind: u.kind, url: `/api/uploads/${u.id}` })),
    });
  } catch (e) {
    return jsonError(e);
  }
}
