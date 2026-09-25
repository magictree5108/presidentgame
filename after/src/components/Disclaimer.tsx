import { DISCLAIMER } from "../../content/legal/disclaimer";

/** 결과 화면 상단에 항상 보이는 시뮬레이션 고지 */
export function DisclaimerBanner({ long = false }: { long?: boolean }) {
  return (
    <div role="note" className="rounded-xl bg-accent-soft px-3 py-2 text-xs leading-relaxed text-ink">
      <span className="font-semibold">AI 시뮬레이션</span> · {long ? DISCLAIMER.long : DISCLAIMER.short}
    </div>
  );
}
