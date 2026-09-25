/**
 * 브랜드 상수. 브랜드명이 바뀌면 이 파일만 고치면 된다.
 */
export const BRAND = {
  /** 서비스 이름 */
  name: "애프터",
  /** 영문 표기 (워터마크, OG 등에서 보조로 사용) */
  nameEn: "AFTER",
  /** 한 줄 설명 (랜딩, OG description) */
  tagline: "성형 후 내 얼굴, 어디까지 할지 친구한테 물어봐.",
  /** 랜딩 보조 설명 */
  subline: "약·중·강 세 가지 버전을 AI로 미리 보고, 그 얼굴로 찍은 인생샷까지. 링크 하나로 친구 투표.",
  /** 강조색 하나. Tailwind 토큰 --color-accent 와 같은 값 */
  accent: "#ff4d6d",
  /** 워터마크 하단 고정 문구 (지울 수 없게 이미지에 굽는다) */
  watermarkNotice: "AI 시뮬레이션이며 실제 의료 결과가 아닙니다",
} as const;

/** 배포 URL. OG 태그, 공유 링크에 쓰인다. */
export function appUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_APP_URL ||
    (process.env.VERCEL_PROJECT_PRODUCTION_URL
      ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
      : process.env.VERCEL_URL
        ? `https://${process.env.VERCEL_URL}`
        : "http://localhost:3000");
  return raw.replace(/\/$/, "");
}
