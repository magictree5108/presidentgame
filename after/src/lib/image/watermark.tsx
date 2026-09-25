import sharp from "sharp";
import { BRAND } from "@/lib/brand";
import { Box, renderPng } from "./render";

/**
 * 워터마크 굽기. 모든 생성 이미지는 저장 전에 반드시 이 함수를 지난다.
 * 하단에 불투명한 띠를 얹고 브랜드명과 고지 문구를 그린다. 이미지 픽셀에 합성되므로 지울 수 없다.
 */
export async function applyWatermark(input: Buffer): Promise<Buffer> {
  const base = sharp(input).rotate();
  const meta = await base.metadata();
  const w = meta.width ?? 1024;
  const h = meta.height ?? 1024;

  // 띠 높이: 이미지 높이의 9%, 72~150px 사이
  const barH = Math.round(Math.min(150, Math.max(72, h * 0.09)));
  const brandSize = Math.round(barH * 0.34);
  const noticeSize = Math.round(barH * 0.24);

  const bar = await renderPng(
    <Box
      style={{
        width: w,
        height: barH,
        background: "rgba(0,0,0,0.82)",
        flexDirection: "column",
        justifyContent: "center",
        paddingLeft: Math.round(w * 0.04),
        paddingRight: Math.round(w * 0.04),
        fontFamily: "Pretendard",
        color: "#fff",
      }}
    >
      <Box style={{ alignItems: "baseline", gap: 10 }}>
        <span style={{ fontSize: brandSize, fontWeight: 700, letterSpacing: -0.5 }}>{BRAND.name}</span>
        <span style={{ fontSize: Math.round(brandSize * 0.7), color: BRAND.accent, fontWeight: 700 }}>{BRAND.nameEn}</span>
      </Box>
      <span style={{ fontSize: noticeSize, opacity: 0.92, marginTop: 2 }}>{BRAND.watermarkNotice}</span>
    </Box>,
    w,
    barH,
  );

  return base
    .composite([{ input: bar, left: 0, top: h - barH }])
    .jpeg({ quality: 90, mozjpeg: true })
    .toBuffer();
}
