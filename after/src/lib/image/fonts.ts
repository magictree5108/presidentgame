import { promises as fs } from "node:fs";
import path from "node:path";
import type { Font } from "satori";

/**
 * 서버에서 텍스트를 이미지에 그릴 때 쓰는 한글 폰트 (Pretendard, SIL OFL).
 * Vercel 서버리스 번들에 포함되도록 next.config.ts 의 outputFileTracingIncludes 에 등록돼 있다.
 */
const FONT_DIR = path.join(process.cwd(), "src", "assets", "fonts");

let cached: Font[] | null = null;

export async function loadFonts(): Promise<Font[]> {
  if (cached) return cached;
  const [regular, bold] = await Promise.all([
    fs.readFile(path.join(FONT_DIR, "Pretendard-Regular.otf")),
    fs.readFile(path.join(FONT_DIR, "Pretendard-Bold.otf")),
  ]);
  cached = [
    { name: "Pretendard", data: regular, weight: 400, style: "normal" },
    { name: "Pretendard", data: bold, weight: 700, style: "normal" },
  ];
  return cached;
}
