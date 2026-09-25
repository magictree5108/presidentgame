/**
 * 서비스 정책 상수. 크레딧, 보관 기간, 분당 제한, 이미지 규격.
 * 값을 바꾸면 서버 로직과 UI 문구가 함께 따라간다.
 */
export const POLICY = {
  /** 신규 세션 무료 크레딧 */
  freeCredits: {
    face: 1, // 성형 후 얼굴 생성 1회
    photo: 4, // 인생샷 4장 = 한 세트
  },
  /** 인생샷 한 세트 장수 */
  photosPerSet: 4,
  /** 원본 사진 보관 시간 (시간 단위) */
  originalRetentionHours: 24,
  /** 생성 이미지·공유 카드 보관 시간 (시간 단위). 공유 링크 수명과 같다. */
  generatedRetentionHours: 24 * 7,
  /** 세션당 분당 생성 요청 제한 */
  rateLimit: {
    perMinute: 5,
    windowSeconds: 60,
  },
  /** 업로드 이미지 최대 변 길이 (px). 서버에서 리사이즈한다. */
  uploadMaxEdge: 1536,
  /** 업로드 허용 최대 용량 (bytes) */
  uploadMaxBytes: 12 * 1024 * 1024,
  /** 측면 사진 최대 장수 */
  maxSidePhotos: 2,
} as const;

export type CreditKind = keyof typeof POLICY.freeCredits;
