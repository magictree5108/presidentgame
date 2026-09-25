"use client";
import type { VoteChoiceView } from "@/lib/client/session";

/** 투표 집계 막대. 공유 페이지(투표 후)와 주인의 결과 화면에서 같이 쓴다. */
export function VoteTally({
  question,
  choices,
  tally,
  total,
  mine,
  onRefresh,
}: {
  question: string;
  choices: VoteChoiceView[];
  tally: Record<string, number>;
  total: number;
  mine?: string | null;
  onRefresh?: () => void;
}) {
  const top = choices.reduce<string | null>((best, c) => ((tally[c.id] ?? 0) > (best ? tally[best] ?? 0 : -1) ? c.id : best), null);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-semibold">{question}</p>
        <span className="text-xs text-muted">{total}명 투표</span>
      </div>
      {total === 0 ? <p className="rounded-xl bg-surface px-3 py-2 text-xs text-muted">아직 투표가 없어요. 링크를 친구에게 보내 보세요.</p> : null}
      {choices.map((c) => {
        const n = tally[c.id] ?? 0;
        const pct = total ? Math.round((n / total) * 100) : 0;
        const isTop = total > 0 && c.id === top;
        return (
          <div key={c.id} className="relative overflow-hidden rounded-xl bg-surface">
            <div className={`absolute inset-y-0 left-0 ${isTop ? "bg-accent/20" : "bg-line/70"}`} style={{ width: `${pct}%` }} />
            <div className="relative flex items-center justify-between px-3 py-2 text-sm">
              <span className={isTop ? "font-semibold" : ""}>
                {c.emoji} {c.label}
                {mine === c.id ? <span className="ml-1 text-[11px] text-accent">내 선택</span> : null}
              </span>
              <span className="text-xs text-muted">
                {pct}% · {n}
              </span>
            </div>
          </div>
        );
      })}
      {onRefresh ? (
        <button onClick={onRefresh} className="self-end text-xs text-muted underline underline-offset-2">
          새로고침
        </button>
      ) : null}
    </div>
  );
}
