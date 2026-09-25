"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { PaywallModal } from "@/components/PaywallModal";
import { useSession } from "@/lib/client/session";
import {
  INTENSITIES,
  INTENSITY_LABELS,
  PART_LABELS,
  PRESETS,
  PRESET_IDS,
  PRESET_LABELS,
  SURGERY_PARTS,
  describeSelection,
  type Intensity,
  type PresetId,
  type SurgerySelection,
} from "../../../prompts/surgery";

/**
 * 시술 선택. 프리셋 세 개는 시작점이고, 그 아래 다섯 부위는 항상 각각 켜고 끄고 강도를 고를 수 있다.
 */
export default function SelectPage() {
  const router = useRouter();
  const { session } = useSession();
  const [preset, setPreset] = useState<PresetId>("natural");
  const [sel, setSel] = useState<SurgerySelection>(PRESETS.natural);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [paywall, setPaywall] = useState(false);
  const [compare, setCompare] = useState(true);

  useEffect(() => {
    if (session === null) router.replace("/");
    if (session && !session.uploads.some((u) => u.kind === "front")) router.replace("/upload");
  }, [session, router]);

  const applyPreset = (id: PresetId) => {
    setPreset(id);
    setSel(PRESETS[id]);
  };
  const toggle = (p: keyof SurgerySelection) => {
    setPreset("custom");
    setSel((s) => ({ ...s, [p]: { ...s[p], enabled: !s[p].enabled } }));
  };
  const setIntensity = (p: keyof SurgerySelection, i: Intensity) => {
    setPreset("custom");
    setSel((s) => ({ ...s, [p]: { enabled: true, intensity: i } }));
  };

  const anyEnabled = SURGERY_PARTS.some((p) => sel[p].enabled);

  const generate = async () => {
    setBusy(true);
    setErr("");
    const res = await fetch("/api/generate/face", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selection: sel, compare }),
    });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (res.status === 402) return setPaywall(true);
    if (!res.ok) return setErr(data.error ?? "생성을 시작하지 못했어요.");
    router.push(`/face?g=${data.generation.id}`);
  };

  return (
    <Shell step="2 / 3 시술 선택">
      <section>
        <h1 className="text-2xl font-bold tracking-tight">어떻게 바꿔 볼까요?</h1>
        <p className="mt-1 text-sm text-muted">프리셋을 고르고, 아래에서 부위마다 직접 조절할 수 있어요.</p>
      </section>

      <div className="grid grid-cols-3 gap-2">
        {PRESET_IDS.map((id) => (
          <button
            key={id}
            onClick={() => applyPreset(id)}
            className={`card flex flex-col items-start gap-1 text-left transition ${preset === id ? "border-ink ring-1 ring-ink" : ""}`}
          >
            <span className="text-sm font-bold">{PRESET_LABELS[id].title}</span>
            <span className="text-[11px] leading-snug text-muted">{PRESET_LABELS[id].description}</span>
          </button>
        ))}
      </div>

      <ul className="flex flex-col gap-2">
        {SURGERY_PARTS.map((p) => {
          const on = sel[p].enabled;
          return (
            <li key={p} className={`card flex items-center justify-between gap-3 ${on ? "" : "opacity-70"}`}>
              <button
                onClick={() => toggle(p)}
                aria-pressed={on}
                className={`flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold transition ${on ? "bg-ink text-white" : "bg-surface text-muted"}`}
              >
                <span className={`h-2 w-2 rounded-full ${on ? "bg-accent" : "bg-line"}`} />
                {PART_LABELS[p]}
              </button>
              <div className="flex rounded-full bg-surface p-1" role="radiogroup" aria-label={`${PART_LABELS[p]} 강도`}>
                {INTENSITIES.map((i) => (
                  <button
                    key={i}
                    role="radio"
                    aria-checked={on && sel[p].intensity === i}
                    onClick={() => setIntensity(p, i)}
                    className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${on && sel[p].intensity === i ? "bg-white text-ink shadow" : "text-muted"}`}
                  >
                    {INTENSITY_LABELS[i]}
                  </button>
                ))}
              </div>
            </li>
          );
        })}
      </ul>

      <label className={`card flex cursor-pointer items-start gap-3 ${compare ? "border-ink" : ""}`}>
        <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} className="mt-1 h-5 w-5 accent-[var(--color-accent)]" />
        <span>
          <span className="block text-sm font-semibold">약·중·강 세 장을 한 번에 비교하기 <span className="ml-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent">추천</span></span>
          <span className="mt-0.5 block text-xs leading-relaxed text-muted">
            켠 부위를 세 강도로 각각 만들어요. 크레딧은 1회만 써요. 친구 투표로 어디까지 할지 물어볼 수 있어요.
            {compare ? " 위에서 고른 강도는 무시돼요." : ""}
          </span>
        </span>
      </label>

      <div className="rounded-xl bg-surface px-4 py-3 text-sm">
        <span className="text-muted">선택: </span>
        <span className="font-semibold">{compare ? SURGERY_PARTS.filter((p) => sel[p].enabled).map((p) => PART_LABELS[p]).join(" · ") + " · 약/중/강 비교" : describeSelection(sel)}</span>
      </div>

      {err ? <p className="text-sm font-medium text-accent">{err}</p> : null}
      <button onClick={generate} disabled={!anyEnabled || busy} className="btn btn-accent">
        {busy ? "시작하는 중…" : compare ? "세 가지 버전 만들기" : "성형 후 얼굴 만들기"}
      </button>
      <p className="text-center text-xs text-muted">
        남은 무료 얼굴 생성 {session?.credits.face ?? "-"}회 · 결과는 AI 시뮬레이션이에요
      </p>
      <PaywallModal open={paywall} onClose={() => setPaywall(false)} kind="face" />
    </Shell>
  );
}
