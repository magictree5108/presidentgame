/**
 * 공유 페이지 투표 정의. 서버(검증·집계)와 클라이언트(버튼)가 같이 쓴다.
 *  - 비교 모드(강도 3장): "어디까지 하는 게 제일 나아?" → 약 / 중 / 강 / 안 하는 게 나아
 *  - 단일 모드: "이렇게 바꿔볼까?" → 해! / 좀 더 고민
 */
export type VoteChoice = { id: string; label: string; emoji: string };

export const NONE_CHOICE: VoteChoice = { id: "none", label: "안 하는 게 나아", emoji: "🙅" };

export function voteQuestion(variantCount: number): string {
  return variantCount >= 2 ? "어디까지 하는 게 제일 나아?" : "이렇게 바꿔볼까?";
}

export function voteChoices(variantLabels: string[]): VoteChoice[] {
  if (variantLabels.length >= 2) {
    const emojis = ["🌱", "✨", "🔥"];
    return [
      ...variantLabels.map((label, i) => ({ id: String(i), label, emoji: emojis[i] ?? "•" })),
      NONE_CHOICE,
    ];
  }
  return [
    { id: "yes", label: "해!", emoji: "👍" },
    { id: "hmm", label: "좀 더 고민", emoji: "🤔" },
  ];
}

export function isValidChoice(variantLabels: string[], id: string): boolean {
  return voteChoices(variantLabels).some((c) => c.id === id);
}
