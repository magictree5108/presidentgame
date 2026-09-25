/**
 * 성형 후 얼굴 생성 프롬프트 템플릿 (FLUX.1 Kontext 계열 편집 모델용)
 *
 * 구조 원칙
 * 1. 보존 지시를 먼저 쓴다. 편집 모델은 "무엇을 유지할지"를 앞에 두면 정체성 붕괴가 줄어든다.
 * 2. 변경 지시는 마지막에 쓴다. 선택된 부위만 나열하고, 선택되지 않은 부위는
 *    "unchanged" 목록에 명시적으로 넣어 모델이 건드리지 않게 한다.
 * 3. 영어로 쓴다. Kontext는 영어 프롬프트에서 편집 정확도가 가장 높다.
 *
 * 조합 규칙 (부위 × 강도 → 문장)
 * - 부위(part): nose, eyes, jawline, forehead, lips 다섯 가지
 * - 강도(intensity): low(약), mid(중), high(강)
 * - 각 부위에 강도별 문장이 하나씩 있다. 켜진 부위의 문장만 뽑아서 "Edits:" 뒤에 이어 붙인다.
 * - 예) eyes=mid, nose=low, 나머지 off
 *      → "Edits: Make the eyes moderately larger ... . Slightly refine the nose bridge ... .
 *         Keep the jawline, forehead, and lips exactly as they are."
 *
 * 프리셋은 이 파일 하단 PRESETS 에 정의한다. 프리셋을 고르면 다섯 부위의 on/off 와 강도가
 * 그 값으로 채워지고, 사용자는 그 위에서 부위별로 다시 조절할 수 있다.
 */

export const SURGERY_PARTS = ["nose", "eyes", "jawline", "forehead", "lips"] as const;
export type SurgeryPart = (typeof SURGERY_PARTS)[number];

export const INTENSITIES = ["low", "mid", "high"] as const;
export type Intensity = (typeof INTENSITIES)[number];

/** UI 표시용 한국어 라벨 */
export const PART_LABELS: Record<SurgeryPart, string> = {
  nose: "코",
  eyes: "눈",
  jawline: "턱선",
  forehead: "이마",
  lips: "입술",
};

export const INTENSITY_LABELS: Record<Intensity, string> = {
  low: "약",
  mid: "중",
  high: "강",
};

/** 사용자의 선택값. 부위별로 켜짐 여부와 강도. */
export type SurgerySelection = Record<SurgeryPart, { enabled: boolean; intensity: Intensity }>;

/**
 * 부위 × 강도 문장표.
 * 각 문장은 "무엇을, 얼마나" 를 한 문장으로 말하고, 자연스러움을 함께 요구한다.
 * 강도가 올라갈수록 형용사(slightly → moderately → clearly/noticeably)와 구체 수치 표현이 세진다.
 */
const PART_SENTENCES: Record<SurgeryPart, Record<Intensity, string>> = {
  nose: {
    low: "Slightly refine the nose: make the bridge a touch straighter and the tip a little more defined, keeping the overall nose size the same.",
    mid: "Moderately refine the nose: narrow the bridge and nostrils a bit, lift and define the tip so it looks sculpted but still natural.",
    high: "Clearly reshape the nose into a slimmer, higher, straight bridge with a lifted, well-defined tip and narrower nostrils, as after rhinoplasty, while keeping it realistic for this face.",
  },
  eyes: {
    low: "Slightly enlarge the eyes with a subtle, natural double eyelid crease, keeping the eye shape and spacing the same.",
    mid: "Moderately enlarge the eyes with a clear natural double eyelid crease and a slightly more open, brighter look, keeping the eye spacing the same.",
    high: "Noticeably enlarge the eyes with a defined double eyelid crease, gently open the inner corners, and make the eyes look brighter and more awake, as after double eyelid and epicanthoplasty surgery, still realistic.",
  },
  jawline: {
    low: "Slightly slim the lower face: soften the jaw angle a little for a smoother jawline, keeping the chin length the same.",
    mid: "Moderately slim the jawline into a smoother V-line, reduce the jaw angle width, and keep the chin natural.",
    high: "Clearly slim the jawline into a sharp V-line with a narrower lower face and refined chin, as after jaw contouring surgery, while keeping proportions realistic.",
  },
  forehead: {
    low: "Slightly smooth and round the forehead so it looks a little fuller and more even, keeping the hairline the same.",
    mid: "Moderately round out the forehead so it looks fuller and smoothly curved, keeping the hairline the same.",
    high: "Clearly give the forehead a full, smoothly rounded, volumized shape as after forehead augmentation, keeping the hairline the same and realistic.",
  },
  lips: {
    low: "Slightly plump the lips with a little more volume and a softer, well-defined lip line, keeping the mouth width the same.",
    mid: "Moderately plump the lips with fuller volume, a defined cupid's bow, and a smooth lip line, keeping the mouth width the same.",
    high: "Noticeably plump the lips with full, well-shaped volume and a crisp cupid's bow, as after lip filler, still proportional and realistic.",
  },
};

/** "그대로 둬라" 목록에 쓰는 영어 명칭 */
const PART_NOUNS: Record<SurgeryPart, string> = {
  nose: "nose",
  eyes: "eyes",
  jawline: "jawline and chin",
  forehead: "forehead",
  lips: "lips",
};

/**
 * 보존 지시. 항상 프롬프트 맨 앞에 온다.
 * 정체성(같은 사람), 피부 질감, 표정, 헤어, 배경, 조명, 카메라 앵글을 모두 고정한다.
 */
const PRESERVE_BLOCK = [
  "Edit this portrait photo of a person.",
  "This must remain the exact same person, clearly recognizable, with the same identity, face shape, skin tone, skin texture, pores, moles and freckles.",
  "Keep the same facial expression, gaze direction, head pose, hairstyle, hair color, clothing, accessories, background, lighting, camera angle, framing and photo quality.",
  "Do not beautify or retouch anything that is not listed below. No makeup changes, no skin smoothing, no age change.",
  "The result must look like a real, unedited photograph, not a painting or render.",
].join(" ");

/**
 * 선택값을 최종 프롬프트로 변환한다.
 * [보존 지시] → [변경 지시: 켜진 부위 문장들] → [건드리지 말 것: 꺼진 부위 목록]
 */
export function buildSurgeryPrompt(selection: SurgerySelection): string {
  const enabled = SURGERY_PARTS.filter((p) => selection[p].enabled);
  const disabled = SURGERY_PARTS.filter((p) => !selection[p].enabled);

  if (enabled.length === 0) {
    // 아무것도 안 골랐으면 호출하지 않는 것이 맞지만, 방어적으로 아무 변화 없는 프롬프트를 만든다.
    return `${PRESERVE_BLOCK} Edits: none. Return the photo unchanged.`;
  }

  const edits = enabled.map((p) => PART_SENTENCES[p][selection[p].intensity]).join(" ");
  const keep =
    disabled.length > 0
      ? ` Keep the ${listWithAnd(disabled.map((p) => PART_NOUNS[p]))} exactly as they are.`
      : "";

  return `${PRESERVE_BLOCK} Edits: ${edits}${keep}`;
}

function listWithAnd(items: string[]): string {
  if (items.length <= 1) return items.join("");
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

/**
 * 프리셋. 값은 시작점일 뿐이고, 사용자는 부위별 버튼과 강도로 다시 조절할 수 있다.
 * - natural(자연스럽게): 눈·코·턱선 약. 이마·입술은 끔.
 * - bold(확실하게): 눈·코·턱선·입술 중. 이마는 끔.
 * - custom(내가 고르기): 모두 끔에서 시작.
 */
export const PRESET_IDS = ["natural", "bold", "custom"] as const;
export type PresetId = (typeof PRESET_IDS)[number];

export const PRESET_LABELS: Record<PresetId, { title: string; description: string }> = {
  natural: { title: "자연스럽게", description: "눈·코·턱선을 약하게. 티 안 나게 달라진 느낌." },
  bold: { title: "확실하게", description: "눈·코·턱선·입술을 중간 강도로. 확실히 달라진 느낌." },
  custom: { title: "내가 고르기", description: "부위마다 켜고 끄고 강도를 직접 골라요." },
};

function sel(
  parts: Partial<Record<SurgeryPart, Intensity>>,
): SurgerySelection {
  const out = {} as SurgerySelection;
  for (const p of SURGERY_PARTS) {
    const i = parts[p];
    out[p] = i ? { enabled: true, intensity: i } : { enabled: false, intensity: "mid" };
  }
  return out;
}

export const PRESETS: Record<PresetId, SurgerySelection> = {
  natural: sel({ eyes: "low", nose: "low", jawline: "low" }),
  bold: sel({ eyes: "mid", nose: "mid", jawline: "mid", lips: "mid" }),
  custom: sel({}),
};

/** 선택값을 사람이 읽는 한국어 요약으로. 결과 화면과 공유 카드 라벨에 쓴다. */
export function describeSelection(selection: SurgerySelection): string {
  const parts = SURGERY_PARTS.filter((p) => selection[p].enabled).map(
    (p) => `${PART_LABELS[p]} ${INTENSITY_LABELS[selection[p].intensity]}`,
  );
  return parts.length ? parts.join(" · ") : "변경 없음";
}
