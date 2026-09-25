import sharp, { type OverlayOptions } from "sharp";
import { BRAND } from "@/lib/brand";
import { Box, renderPng } from "./render";
import { applyWatermark } from "./watermark";

/**
 * 공유 카드 합성.
 *  - 스토리 슬라이드: 1080x1920 (인스타 스토리 규격). 1장 = 비포/애프터, 2~5장 = 인생샷.
 *  - OG 이미지: 1200x630. 애프터 얼굴 + 인생샷 4장. 원본은 절대 넣지 않는다.
 * 모든 결과물은 마지막에 applyWatermark 를 지난다.
 */

export const STORY_W = 1080;
export const STORY_H = 1920;
export const OG_W = 1200;
export const OG_H = 630;

const BG = "#ffffff";
const INK = "#111111";

async function cover(buf: Buffer, w: number, h: number, radius = 0): Promise<Buffer> {
  const img = sharp(buf).rotate().resize(w, h, { fit: "cover", position: "attention" });
  if (!radius) return img.png().toBuffer();
  const mask = Buffer.from(
    `<svg width="${w}" height="${h}"><rect x="0" y="0" width="${w}" height="${h}" rx="${radius}" ry="${radius}" fill="#fff"/></svg>`,
  );
  return img.composite([{ input: mask, blend: "dest-in" }]).png().toBuffer();
}

function Header(props: { title: string; subtitle?: string }) {
  return (
    <Box style={{ flexDirection: "column", paddingLeft: 72, paddingRight: 72, paddingTop: 96 }}>
      <Box style={{ alignItems: "baseline", gap: 14 }}>
        <span style={{ fontSize: 44, fontWeight: 700, color: INK, letterSpacing: -1 }}>{BRAND.name}</span>
        <span style={{ fontSize: 28, fontWeight: 700, color: BRAND.accent }}>{BRAND.nameEn}</span>
      </Box>
      <span style={{ fontSize: 58, fontWeight: 700, color: INK, marginTop: 28, letterSpacing: -1.5, lineHeight: 1.2 }}>{props.title}</span>
      {props.subtitle ? <span style={{ fontSize: 30, color: "#555", marginTop: 14 }}>{props.subtitle}</span> : null}
    </Box>
  );
}

/** 슬라이드 1: 비포/애프터 나란히. 원본이 들어가므로 이 파일은 private 버킷에만 저장된다. */
export async function composeBeforeAfterStory(opts: { before: Buffer; after: Buffer; caption: string }): Promise<Buffer> {
  const imgW = 492;
  const imgH = 656;
  const gap = 24;
  const left = Math.round((STORY_W - (imgW * 2 + gap)) / 2);
  const top = 420;

  const [before, after] = await Promise.all([cover(opts.before, imgW, imgH, 28), cover(opts.after, imgW, imgH, 28)]);

  const overlay = await renderPng(
    <Box style={{ width: STORY_W, height: STORY_H, flexDirection: "column", fontFamily: "Pretendard" }}>
      <Header title={"성형 후 내 모습,\n미리 보기"} subtitle={opts.caption} />
      <Box style={{ position: "absolute", top: top - 56, left, width: imgW, justifyContent: "center" }}>
        <span style={{ fontSize: 30, fontWeight: 700, color: "#888", letterSpacing: 4 }}>BEFORE</span>
      </Box>
      <Box style={{ position: "absolute", top: top - 56, left: left + imgW + gap, width: imgW, justifyContent: "center" }}>
        <span style={{ fontSize: 30, fontWeight: 700, color: BRAND.accent, letterSpacing: 4 }}>AFTER</span>
      </Box>
      <Box style={{ position: "absolute", top: top + imgH + 72, left: 72, right: 72, flexDirection: "column", gap: 12 }}>
        <span style={{ fontSize: 34, color: INK, fontWeight: 700 }}>나도 해보기 → 링크는 프로필에</span>
        <span style={{ fontSize: 26, color: "#777" }}>{BRAND.tagline}</span>
      </Box>
    </Box>,
    STORY_W,
    STORY_H,
  );

  const composed = await sharp({ create: { width: STORY_W, height: STORY_H, channels: 3, background: BG } })
    .composite([
      { input: before, left, top },
      { input: after, left: left + imgW + gap, top },
      { input: overlay, left: 0, top: 0 },
    ])
    .jpeg({ quality: 92 })
    .toBuffer();
  return applyWatermark(composed);
}

/** 슬라이드 2~5: 인생샷 한 장을 크게. */
export async function composePhotoStory(opts: { photo: Buffer; caption: string; index: number; total: number }): Promise<Buffer> {
  const photoH = 1500;
  const photo = await cover(opts.photo, STORY_W, photoH);

  const overlay = await renderPng(
    <Box style={{ width: STORY_W, height: STORY_H, flexDirection: "column", fontFamily: "Pretendard" }}>
      <Box style={{ position: "absolute", top: 56, left: 60, alignItems: "center", gap: 12 }}>
        <Box style={{ background: "rgba(0,0,0,0.55)", borderRadius: 999, paddingLeft: 22, paddingRight: 22, paddingTop: 10, paddingBottom: 10 }}>
          <span style={{ fontSize: 28, fontWeight: 700, color: "#fff" }}>{BRAND.name}</span>
        </Box>
        <Box style={{ background: "rgba(0,0,0,0.55)", borderRadius: 999, paddingLeft: 22, paddingRight: 22, paddingTop: 10, paddingBottom: 10 }}>
          <span style={{ fontSize: 26, color: "#fff" }}>{`${opts.index}/${opts.total}`}</span>
        </Box>
      </Box>
      <Box style={{ position: "absolute", top: photoH + 48, left: 72, right: 72, flexDirection: "column", gap: 10 }}>
        <span style={{ fontSize: 44, fontWeight: 700, color: INK, letterSpacing: -1 }}>{opts.caption}</span>
        <span style={{ fontSize: 28, color: "#777" }}>성형 후 얼굴로 찍은 AI 인생샷</span>
      </Box>
    </Box>,
    STORY_W,
    STORY_H,
  );

  const composed = await sharp({ create: { width: STORY_W, height: STORY_H, channels: 3, background: BG } })
    .composite([
      { input: photo, left: 0, top: 0 },
      { input: overlay, left: 0, top: 0 },
    ])
    .jpeg({ quality: 92 })
    .toBuffer();
  return applyWatermark(composed);
}

/** OG 이미지 1200x630: 왼쪽 애프터 얼굴, 오른쪽 인생샷 2x2. */
export async function composeOg(opts: { after: Buffer; photos: Buffer[]; caption: string }): Promise<Buffer> {
  const faceW = 472;
  const cellW = (OG_W - faceW) / 2; // 364
  const cellH = OG_H / 2; // 315
  const face = await cover(opts.after, faceW, OG_H);
  const cells = await Promise.all(opts.photos.slice(0, 4).map((p) => cover(p, Math.floor(cellW), Math.floor(cellH))));

  const layers: OverlayOptions[] = [{ input: face, left: 0, top: 0 }];
  cells.forEach((c, i) => {
    layers.push({ input: c, left: faceW + (i % 2) * Math.floor(cellW), top: Math.floor(i / 2) * Math.floor(cellH) });
  });

  const overlay = await renderPng(
    <Box style={{ width: OG_W, height: OG_H, fontFamily: "Pretendard" }}>
      {/* 하단 72px 은 워터마크 띠가 덮으므로 라벨은 그 위에 놓는다 */}
      <Box
        style={{
          position: "absolute",
          left: 0,
          top: OG_H - 72 - 140,
          width: faceW,
          height: 140,
          background: "linear-gradient(to bottom, rgba(0,0,0,0), rgba(0,0,0,0.7))",
          flexDirection: "column",
          justifyContent: "flex-end",
          paddingLeft: 24,
          paddingBottom: 14,
        }}
      >
        <span style={{ fontSize: 30, fontWeight: 700, color: "#fff" }}>{BRAND.name}</span>
        <span style={{ fontSize: 20, color: "#eee", marginTop: 4 }}>{opts.caption}</span>
      </Box>
    </Box>,
    OG_W,
    OG_H,
  );
  layers.push({ input: overlay, left: 0, top: 0 });

  const composed = await sharp({ create: { width: OG_W, height: OG_H, channels: 3, background: BG } })
    .composite(layers)
    .jpeg({ quality: 88 })
    .toBuffer();
  return applyWatermark(composed);
}
