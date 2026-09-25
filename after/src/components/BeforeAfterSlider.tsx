"use client";
import { useState } from "react";

/** 비포/애프터 슬라이더. 가운데 손잡이를 좌우로 끌면 경계가 움직인다. */
export function BeforeAfterSlider({ before, after }: { before: string; after: string }) {
  const [pos, setPos] = useState(50);
  return (
    <div className="relative w-full select-none overflow-hidden rounded-2xl bg-surface" style={{ aspectRatio: "3 / 4" }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={after} alt="성형 후 시뮬레이션" className="absolute inset-0 h-full w-full object-cover" draggable={false} />
      <div className="absolute inset-0 overflow-hidden" style={{ width: `${pos}%` }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={before}
          alt="원본"
          className="absolute inset-0 h-full max-w-none object-cover"
          style={{ width: `${10000 / pos}%` }}
          draggable={false}
        />
      </div>
      <div className="pointer-events-none absolute inset-y-0" style={{ left: `calc(${pos}% - 1px)` }}>
        <div className="h-full w-0.5 bg-white shadow" />
        <div className="absolute top-1/2 left-1/2 flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white text-sm font-bold shadow">
          ↔
        </div>
      </div>
      <span className="absolute top-3 left-3 rounded-full bg-black/60 px-2.5 py-1 text-xs font-semibold text-white">BEFORE</span>
      <span className="absolute top-3 right-3 rounded-full bg-accent px-2.5 py-1 text-xs font-semibold text-white">AFTER</span>
      <input
        type="range"
        min={2}
        max={98}
        value={pos}
        onChange={(e) => setPos(Number(e.target.value))}
        aria-label="비포 애프터 비교"
        className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0"
      />
    </div>
  );
}
