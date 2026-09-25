import sharp from "sharp";
import { POLICY } from "@/lib/config";

/**
 * 업로드 원본 정규화: EXIF 회전 반영, 최대 변 길이 제한, EXIF 제거, JPEG 변환.
 * 메타데이터(위치 정보 등)가 남지 않게 한다.
 */
export async function normalizeUpload(input: Buffer): Promise<{ buffer: Buffer; width: number; height: number }> {
  const img = sharp(input, { failOn: "none" }).rotate();
  const meta = await img.metadata();
  if (!meta.width || !meta.height) throw new Error("이미지를 읽을 수 없어요.");
  const out = await img
    .resize({ width: POLICY.uploadMaxEdge, height: POLICY.uploadMaxEdge, fit: "inside", withoutEnlargement: true })
    .jpeg({ quality: 90, mozjpeg: true })
    .toBuffer({ resolveWithObject: true });
  return { buffer: out.data, width: out.info.width, height: out.info.height };
}

export async function fetchImageBuffer(url: string): Promise<Buffer> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`이미지를 내려받지 못했어요 (${res.status})`);
  return Buffer.from(await res.arrayBuffer());
}
