/**
 * 인생샷 생성 프롬프트 템플릿 (Nano Banana 계열 멀티 레퍼런스 편집 모델용)
 *
 * 입력 이미지 순서
 *   image_urls[0] = 성형 후 얼굴 (가장 중요한 레퍼런스)
 *   image_urls[1] = 원본 정면 사진 (얼굴 구조·피부 참고)
 *   image_urls[2..] = 원본 측면 사진 (있을 때만, 얼굴 입체감 참고)
 *
 * 구조 원칙
 * 1. 얼굴 동일성 유지가 최우선이라고 첫 문장에서 못 박는다.
 * 2. 어떤 이미지가 얼굴의 기준인지(첫 번째 이미지) 명시한다.
 * 3. 장소(place) 문장과 분위기(mood) 문장을 이어 붙이고, 마지막에 촬영 품질 지시를 둔다.
 * 4. 4장을 한 번에 요청하므로 "각 장마다 포즈와 구도를 다르게" 를 요구한다.
 *
 * 조합 규칙
 *   prompt = IDENTITY_BLOCK + " " + PLACES[place].scene + " " + MOODS[mood].style + " " + QUALITY_BLOCK
 */

export const PLACE_IDS = ["seongsu_cafe", "jeju_sea", "club", "wedding_guest", "interview_id", "campus_bench"] as const;
export type PlaceId = (typeof PLACE_IDS)[number];

export const MOOD_IDS = ["film", "daylight", "neon"] as const;
export type MoodId = (typeof MOOD_IDS)[number];

export const PLACES: Record<PlaceId, { label: string; emoji: string; scene: string; aspectRatio: "3:4" | "4:5" | "9:16" }> = {
  seongsu_cafe: {
    label: "성수 카페",
    emoji: "☕",
    aspectRatio: "4:5",
    scene:
      "Scene: a trendy minimalist cafe in Seongsu-dong, Seoul, with exposed brick, concrete, big windows, a wooden table and a latte. The person is sitting casually, candid Instagram cafe photo, medium shot, wearing a stylish casual outfit.",
  },
  jeju_sea: {
    label: "제주 바다",
    emoji: "🌊",
    aspectRatio: "4:5",
    scene:
      "Scene: the coast of Jeju Island, Korea, with turquoise sea, black volcanic rocks and a breezy sky. The person is standing by the water with wind in the hair, relaxed travel photo, medium shot, wearing light summery clothes.",
  },
  club: {
    label: "클럽",
    emoji: "🪩",
    aspectRatio: "4:5",
    scene:
      "Scene: a nightclub dance floor with colorful lights, haze and a crowd blurred in the background. The person is in the foreground looking confident and having fun, medium close-up, wearing a fashionable night-out outfit.",
  },
  wedding_guest: {
    label: "결혼식 하객",
    emoji: "💐",
    aspectRatio: "4:5",
    scene:
      "Scene: an elegant wedding hall in Seoul with flowers, soft chandeliers and a decorated aisle in the background. The person is a well-dressed wedding guest in a tasteful semi-formal outfit, smiling politely, medium shot.",
  },
  interview_id: {
    label: "면접 증명사진",
    emoji: "🪪",
    aspectRatio: "3:4",
    scene:
      "Scene: a professional Korean ID / job interview photo. Plain light gray studio background, head-and-shoulders framing, facing the camera directly, neat hair, a dark suit jacket with a white shirt, calm confident expression, even studio lighting.",
  },
  campus_bench: {
    label: "캠퍼스 벤치",
    emoji: "🌳",
    aspectRatio: "4:5",
    scene:
      "Scene: a university campus in Korea, sitting on a wooden bench under trees with a brick building softly blurred behind. The person is holding a coffee or a book, natural student look, casual clothes, medium shot.",
  },
};

export const MOODS: Record<MoodId, { label: string; style: string }> = {
  film: {
    label: "필름 감성",
    style:
      "Style: shot on 35mm film, soft grain, slightly faded warm tones, gentle contrast, nostalgic Korean film-camera aesthetic.",
  },
  daylight: {
    label: "선명한 낮",
    style:
      "Style: bright natural daylight, crisp and clean, true-to-life colors, sharp focus, airy and fresh like a high-end smartphone photo.",
  },
  neon: {
    label: "야간 네온",
    style:
      "Style: night time with neon and city lights, cinematic color grading with magenta and cyan highlights, shallow depth of field, moody but flattering.",
  },
};

/** 얼굴 동일성 최우선 지시. 항상 맨 앞. */
const IDENTITY_BLOCK = [
  "TOP PRIORITY: preserve the exact facial identity of the person in the FIRST reference image.",
  "The output face must be the same person as the first image: same face shape, eyes, nose, lips, jawline, skin tone and skin texture, so that a friend would instantly recognize them.",
  "Use the additional reference images only to understand the person's facial structure and proportions from other angles; the FIRST image is the source of truth for how the face looks now.",
  "Do not idealize, beautify, slim, or age the face beyond the first image. Do not change gender or ethnicity.",
].join(" ");

/** 촬영 품질과 다양성 지시. 항상 맨 뒤. */
const QUALITY_BLOCK = [
  "Generate a realistic photograph of this person in that scene.",
  "Photorealistic, natural skin, correct hands, no text, no watermark, no logos.",
  "Vary the pose, framing and expression slightly between images so they feel like different shots from the same photo session.",
].join(" ");

export function buildLifeshotPrompt(place: PlaceId, mood: MoodId): string {
  return `${IDENTITY_BLOCK} ${PLACES[place].scene} ${MOODS[mood].style} ${QUALITY_BLOCK}`;
}

/** 4장을 요청할 때 각 장에 넣을 변주 힌트. 한 번에 4장 생성이 불가한 모델은 장별로 이 힌트를 붙여 4번 호출한다. */
export const SHOT_VARIATIONS = [
  "Shot 1: looking at the camera with a soft smile.",
  "Shot 2: looking slightly away, candid moment.",
  "Shot 3: closer framing, natural laugh.",
  "Shot 4: wider framing showing more of the scene.",
] as const;
