"use client";
import { useEffect, useState } from "react";
import type { VoteChoiceView } from "@/lib/client/session";
import { VoteTally } from "./VoteTally";

type State = {
  question: string;
  choices: VoteChoiceView[];
  mine: string | null;
  isOwner: boolean;
  tally: Record<string, number> | null;
  total: number | null;
};

/** 공유 페이지 투표. 로그인 없이 한 표. 투표하면 집계가 보인다. */
export function VotePanel({ shareId, question, choices }: { shareId: string; question: string; choices: VoteChoiceView[] }) {
  const [state, setState] = useState<State | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`/api/share/${shareId}/vote`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => alive && !d.error && setState(d))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [shareId]);

  const vote = async (choice: string) => {
    setBusy(true);
    const res = await fetch(`/api/share/${shareId}/vote`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ choice }) });
    const d = await res.json().catch(() => null);
    setBusy(false);
    if (d && !d.error) setState(d);
  };

  const q = state?.question ?? question;
  const cs = state?.choices ?? choices;
  const revealed = !!state?.tally;

  return (
    <section className="card flex flex-col gap-3" id="vote">
      {!revealed ? (
        <>
          <p className="text-base font-bold">{q}</p>
          <div className="grid grid-cols-2 gap-2">
            {cs.map((c) => (
              <button key={c.id} onClick={() => vote(c.id)} disabled={busy} className="btn btn-secondary py-3 text-sm">
                <span className="mr-1.5">{c.emoji}</span>
                {c.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-muted">익명 투표예요. 투표하면 다른 사람들의 선택도 볼 수 있어요.</p>
        </>
      ) : (
        <>
          <VoteTally question={q} choices={cs} tally={state!.tally!} total={state!.total ?? 0} mine={state!.mine} />
          {!state!.isOwner ? (
            <div className="flex flex-wrap gap-1.5">
              {cs.map((c) => (
                <button key={c.id} onClick={() => vote(c.id)} disabled={busy || state!.mine === c.id} className={`chip ${state!.mine === c.id ? "chip-on" : ""}`}>
                  {c.emoji} {c.label}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-muted">내 공유 링크예요. 친구들의 투표가 여기 모여요.</p>
          )}
        </>
      )}
    </section>
  );
}
