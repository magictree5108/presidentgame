"use client";
import { useState } from "react";
import { BRAND } from "@/lib/brand";

/** 크레딧 소진 시 "곧 출시" 안내 + 대기 리스트 이메일 수집 */
export function PaywallModal({ open, onClose, kind }: { open: boolean; onClose: () => void; kind: "face" | "photo" }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");
  if (!open) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setState("sending");
    const res = await fetch("/api/waitlist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
    const data = await res.json().catch(() => ({}));
    if (res.ok) setState("done");
    else {
      setState("error");
      setMsg(data.error ?? "잠시 후 다시 시도해 주세요.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center" onClick={onClose}>
      <div className="w-full max-w-md rounded-3xl bg-white p-6" onClick={(e) => e.stopPropagation()}>
        <p className="text-xs font-bold text-accent">곧 출시</p>
        <h2 className="mt-1 text-xl font-bold">
          무료 {kind === "face" ? "얼굴 생성" : "인생샷"}을 다 썼어요
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          추가 생성은 결제 기능과 함께 곧 열려요. 이메일을 남기면 열리는 날 가장 먼저 알려 드릴게요.
        </p>
        {state === "done" ? (
          <p className="mt-5 rounded-xl bg-surface p-4 text-center text-sm font-semibold">등록됐어요. 곧 만나요!</p>
        ) : (
          <form onSubmit={submit} className="mt-5 flex flex-col gap-2">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="이메일 주소"
              className="rounded-xl border border-line px-4 py-3 text-base outline-none focus:border-ink"
            />
            <button className="btn btn-accent" disabled={state === "sending"}>
              {state === "sending" ? "등록 중…" : "출시 알림 받기"}
            </button>
            {state === "error" ? <p className="text-xs text-accent">{msg}</p> : null}
          </form>
        )}
        <button onClick={onClose} className="mt-3 w-full py-2 text-sm text-muted">
          닫기
        </button>
        <p className="mt-2 text-center text-[11px] text-muted">{BRAND.name}는 특정 병원이나 시술을 추천하지 않아요.</p>
      </div>
    </div>
  );
}
