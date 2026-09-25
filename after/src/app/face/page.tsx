"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { BeforeAfterSlider } from "@/components/BeforeAfterSlider";
import { LoadingSteps } from "@/components/LoadingSteps";
import { DisclaimerBanner } from "@/components/Disclaimer";
import { PaywallModal } from "@/components/PaywallModal";
import { DeleteDataButton } from "@/components/DeleteDataButton";
import { usePollGeneration, useSession, type GenerationView } from "@/lib/client/session";

function FaceResult() {
  const router = useRouter();
  const params = useSearchParams();
  const { session, reload } = useSession();
  const [pickedGenId, setGenId] = useState<string | null>(params.get("g"));
  const [polledCredits, setCredits] = useState<{ face: number; photo: number } | null>(null);
  const genId = pickedGenId ?? session?.face?.id ?? null;
  const credits = polledCredits ?? session?.credits ?? null;
  const [paywall, setPaywall] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pickedIdx, setPickedIdx] = useState<number | null>(null);
  const [choosing, setChoosing] = useState(false);

  useEffect(() => {
    if (session === null) router.replace("/");
    if (session && !genId) router.replace("/select");
  }, [session, genId, router]);

  const gen = usePollGeneration(genId, (_g: GenerationView, c) => c && setCredits(c));
  const front = session?.uploads.find((u) => u.kind === "front");
  const variantLabels = (gen?.params.variantLabels as string[] | undefined) ?? [];
  const isCompare = !!gen && gen.outputs.length >= 2 && variantLabels.length === gen.outputs.length;
  const idx = pickedIdx ?? gen?.chosen ?? (isCompare ? 1 : 0);

  const pick = async (i: number) => {
    setPickedIdx(i);
    if (!isCompare) return;
    setChoosing(true);
    await fetch("/api/generate/face/choose", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ index: i }) });
    setChoosing(false);
  };

  const regenerate = async () => {
    if (!session?.selection) return router.push("/select");
    setBusy(true);
    setErr("");
    const res = await fetch("/api/generate/face", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selection: session.selection }),
    });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (res.status === 402) return setPaywall(true);
    if (!res.ok) return setErr(data.error ?? "재생성을 시작하지 못했어요.");
    await reload();
    router.replace(`/face?g=${data.generation.id}`);
    setGenId(data.generation.id);
  };

  return (
    <Shell step="2 / 3 결과">
      <DisclaimerBanner />
      {!gen || (gen.status !== "done" && gen.status !== "failed") ? (
        <LoadingSteps kind="face" stage={gen?.status ?? "queued"} />
      ) : gen.status === "failed" ? (
        <div className="card flex flex-col gap-3">
          <p className="font-semibold">생성에 실패했어요</p>
          <p className="text-sm text-muted">{gen.error}</p>
          <p className="text-xs text-muted">크레딧은 돌려드렸어요.</p>
          <Link href="/select" className="btn btn-primary">
            다시 시도
          </Link>
        </div>
      ) : (
        <>
          <h1 className="text-2xl font-bold tracking-tight">{isCompare ? "어디까지 할까?" : "성형 후 내 모습"}</h1>
          <p className="-mt-3 text-sm text-muted">{String(gen.params.label ?? "")}</p>
          {front ? <BeforeAfterSlider key={idx} before={front.url} after={gen.outputs[idx]} /> : null}
          <p className="text-center text-xs text-muted">가운데 손잡이를 좌우로 움직여 비교해 보세요</p>

          {isCompare ? (
            <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="강도 선택">
              {gen.outputs.map((u, i) => (
                <button
                  key={u}
                  role="radio"
                  aria-checked={idx === i}
                  onClick={() => pick(i)}
                  className={`overflow-hidden rounded-xl border-2 bg-surface text-left transition ${idx === i ? "border-accent" : "border-transparent"}`}
                >
                  <div style={{ aspectRatio: "3 / 4" }}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={u} alt={`${variantLabels[i]} 강도`} className="h-full w-full object-cover" />
                  </div>
                  <div className={`px-2 py-1.5 text-center text-sm font-semibold ${idx === i ? "bg-accent text-white" : ""}`}>{variantLabels[i]}</div>
                </button>
              ))}
            </div>
          ) : null}

          <Link href="/photos" className="btn btn-accent">
            {isCompare ? `"${variantLabels[idx]}"으로 인생샷 4장 만들기` : "이 얼굴로 인생샷 4장 만들기"}
            {choosing ? " …" : ""}
          </Link>
          {isCompare ? <p className="-mt-3 text-center text-xs text-muted">공유 링크에서는 세 장 모두 보여주고 친구들이 투표해요</p> : null}
          <div className="flex flex-col gap-2">
            <button onClick={regenerate} disabled={busy} className="btn btn-secondary">
              {busy ? "시작하는 중…" : `마음에 안 들어요, 다시 만들기 (남은 ${credits?.face ?? 0}회)`}
            </button>
            <Link href="/select" className="py-2 text-center text-sm text-muted underline underline-offset-2">
              부위·강도 바꾸기
            </Link>
          </div>
          {err ? <p className="text-sm font-medium text-accent">{err}</p> : null}
          <div className="flex justify-center">
            <DeleteDataButton />
          </div>
        </>
      )}
      <PaywallModal open={paywall} onClose={() => setPaywall(false)} kind="face" />
    </Shell>
  );
}

export default function Page() {
  return (
    <Suspense>
      <FaceResult />
    </Suspense>
  );
}
