"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Shell } from "@/components/Shell";
import { BRAND } from "@/lib/brand";
import { AGE_GATE } from "../../content/legal/age-gate";
import { FACE_CONSENT } from "../../content/legal/face-consent";
import { DISCLAIMER } from "../../content/legal/disclaimer";

function Landing() {
  const router = useRouter();
  const params = useSearchParams();
  const [age, setAge] = useState(false);
  const [consent, setConsent] = useState(false);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const start = async () => {
    if (!age) return setErr(AGE_GATE.blockedMessage);
    if (!consent) return setErr(FACE_CONSENT.blockedMessage);
    setErr("");
    setBusy(true);
    const res = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ageConfirmed: true, faceConsent: true }),
    });
    setBusy(false);
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      return setErr(d.error ?? "시작할 수 없어요. 잠시 후 다시 시도해 주세요.");
    }
    router.push("/upload");
  };

  return (
    <Shell showDisclaimer={false}>
      {params.get("deleted") ? (
        <p className="rounded-xl bg-surface px-3 py-2 text-xs">내 데이터가 모두 삭제됐어요.</p>
      ) : null}
      <section className="pt-6">
        <h1 className="text-3xl leading-tight font-bold tracking-tight">
          성형 후 내 얼굴,
          <br />
          미리 보고 <span className="text-accent">인생샷</span>까지.
        </h1>
        <p className="mt-3 text-base leading-relaxed text-muted">{BRAND.tagline}</p>
      </section>

      <ol className="grid grid-cols-3 gap-2 text-center text-xs text-muted">
        {["셀카 올리기", "부위·강도 고르기", "인생샷 4장 받기"].map((t, i) => (
          <li key={t} className="card py-3">
            <span className="block text-lg font-bold text-ink">{i + 1}</span>
            {t}
          </li>
        ))}
      </ol>

      <div className="card flex flex-col gap-4">
        <label className="flex cursor-pointer items-start gap-3">
          <input type="checkbox" checked={age} onChange={(e) => setAge(e.target.checked)} className="mt-1 h-5 w-5 accent-[var(--color-accent)]" />
          <span>
            <span className="block text-sm font-semibold">{AGE_GATE.checkboxLabel}</span>
            <span className="mt-0.5 block text-xs leading-relaxed text-muted">{AGE_GATE.helper}</span>
          </span>
        </label>
        <label className="flex cursor-pointer items-start gap-3">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 h-5 w-5 accent-[var(--color-accent)]" />
          <span>
            <span className="block text-sm font-semibold">{FACE_CONSENT.checkboxLabel}</span>
            <button type="button" onClick={() => setOpen((v) => !v)} className="mt-0.5 text-xs text-muted underline underline-offset-2">
              {open ? "접기" : "어떻게 처리되나요?"}
            </button>
          </span>
        </label>
        {open ? (
          <ul className="list-disc space-y-1 rounded-xl bg-surface p-4 pl-8 text-xs leading-relaxed text-muted">
            {FACE_CONSENT.details.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        ) : null}
      </div>

      {err ? <p className="text-sm font-medium text-accent">{err}</p> : null}
      <button onClick={start} disabled={busy || !age || !consent} className="btn btn-primary">
        {busy ? "준비 중…" : "시작하기"}
      </button>
      <p className="text-center text-xs text-muted">무료로 성형 후 얼굴 1회, 인생샷 4장을 만들 수 있어요.</p>
      <p className="mt-auto pt-6 text-xs leading-relaxed text-muted">{DISCLAIMER.long}</p>
    </Shell>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Landing />
    </Suspense>
  );
}
