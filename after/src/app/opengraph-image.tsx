import { ImageResponse } from "next/og";
import { promises as fs } from "node:fs";
import path from "node:path";
import { BRAND } from "@/lib/brand";

/** 랜딩 링크를 공유했을 때 뜨는 OG 이미지 (빌드 시 정적 생성) */
export const alt = `${BRAND.name} · ${BRAND.tagline}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  const fontDir = path.join(process.cwd(), "src", "assets", "fonts");
  const [regular, bold] = await Promise.all([
    fs.readFile(path.join(fontDir, "Pretendard-Regular.otf")),
    fs.readFile(path.join(fontDir, "Pretendard-Bold.otf")),
  ]);
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: 72, background: "#fff", color: "#111", fontFamily: "Pretendard" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
          <span style={{ fontSize: 48, fontWeight: 700 }}>{BRAND.name}</span>
          <span style={{ fontSize: 30, fontWeight: 700, color: BRAND.accent }}>{BRAND.nameEn}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ display: "flex", flexDirection: "column", fontSize: 76, fontWeight: 700, lineHeight: 1.15, letterSpacing: -2 }}>
            <span>성형, 어디까지 할까?</span>
            <span>친구한테 물어봐.</span>
          </div>
          <span style={{ fontSize: 30, color: "#666" }}>{BRAND.subline}</span>
        </div>
        <span style={{ fontSize: 22, color: "#999" }}>{BRAND.watermarkNotice}</span>
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: "Pretendard", data: regular, weight: 400, style: "normal" },
        { name: "Pretendard", data: bold, weight: 700, style: "normal" },
      ],
    },
  );
}
