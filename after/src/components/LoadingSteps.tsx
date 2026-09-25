"use client";
import { useEffect, useState } from "react";

/**
 * 로딩 중 생성 단계를 문장으로 보여준다.
 * 서버가 내려주는 상태(queued/running/processing)에 맞는 문장 묶음을 2.5초마다 돌린다.
 */
const SENTENCES: Record<"face" | "photo", Record<string, string[]>> = {
  face: {
    queued: ["사진을 확인하고 있어요", "AI 대기열에 올렸어요. 잠시만요"],
    running: ["고른 부위만 조심스럽게 바꾸는 중", "피부 결, 표정, 머리는 그대로 두는 중", "같은 사람처럼 보이는지 맞춰 보는 중"],
    processing: ["결과에 워터마크를 새기는 중", "거의 다 됐어요"],
  },
  photo: {
    queued: ["레퍼런스 사진을 정리하는 중", "AI 대기열에 올렸어요. 잠시만요"],
    running: ["얼굴 동일성을 지키면서 장면을 그리는 중", "조명과 분위기를 맞추는 중", "네 장을 서로 다르게 구성하는 중", "손과 배경 디테일을 다듬는 중"],
    processing: ["네 장에 워터마크를 새기는 중", "거의 다 됐어요"],
  },
};

export function LoadingSteps({ kind, stage }: { kind: "face" | "photo"; stage: string }) {
  const list = SENTENCES[kind][stage] ?? SENTENCES[kind].queued;
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((x) => x + 1), 2500);
    return () => clearInterval(t);
  }, []);
  const i = tick % list.length;
  const order = ["queued", "running", "processing"];
  const idx = Math.max(0, order.indexOf(stage));
  return (
    <div className="card flex flex-col items-center gap-4 py-10 text-center">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-line border-t-accent" />
      <p className="text-base font-semibold">{list[i]}…</p>
      <ol className="flex gap-2 text-xs text-muted">
        {["대기", "생성", "마무리"].map((label, k) => (
          <li key={label} className={k <= idx ? "font-semibold text-ink" : ""}>
            {k + 1}. {label}
          </li>
        ))}
      </ol>
      <p className="text-xs text-muted">보통 20초에서 1분 정도 걸려요. 화면을 닫지 마세요.</p>
    </div>
  );
}
