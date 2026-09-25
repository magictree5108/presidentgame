import satori from "satori";
import sharp from "sharp";
import type { ReactNode } from "react";
import { loadFonts } from "./fonts";

/**
 * satori 로 React 엘리먼트를 SVG 로 렌더링(글자는 path 로 변환되므로 시스템 폰트가 필요 없다)한 뒤
 * sharp 로 PNG 버퍼로 만든다. 워터마크와 공유 카드의 텍스트 레이어는 전부 이 함수를 지난다.
 */
export async function renderPng(element: ReactNode, width: number, height: number): Promise<Buffer> {
  const fonts = await loadFonts();
  const svg = await satori(element, { width, height, fonts });
  return sharp(Buffer.from(svg)).png().toBuffer();
}

/** satori 는 루트가 flex 여야 한다. 공통 래퍼. */
export function Box(props: { style?: Record<string, unknown>; children?: ReactNode }) {
  return <div style={{ display: "flex", ...(props.style ?? {}) }}>{props.children}</div>;
}
