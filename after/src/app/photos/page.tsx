"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { LoadingSteps } from "@/components/LoadingSteps";
import { DisclaimerBanner } from "@/components/Disclaimer";
import { PaywallModal } from "@/components/PaywallModal";
import { DeleteDataButton } from "@/components/DeleteDataButton";
import { usePollGeneration, useSession, type GenerationView, type ShareView } from "@/lib/client/session";
import { VoteTally } from "@/components/VoteTally";
import { MOODS, MOOD_IDS, PLACES, PLACE_IDS, type MoodId, type PlaceId } from "../../../prompts/lifeshot";

function Photos() {
  const router = useRouter();
  const params = useSearchParams();
  const { session, reload } = useSession();
  const [place, setPlace] = useState<PlaceId>("seongsu_cafe");
  const [mood, setMood] = useState<MoodId>("film");
  // genId: 사용자가 명시적으로 초기화(다른 장소로 다시)하면 null 을 유지해야 하므로 세션 값과 분리한다.
  const [pickedGenId, setGenId] = useState<string | null | undefined>(params.get("g") ?? undefined);
  const [polledCredits, setCredits] = useState<{ face: number; photo: number } | null>(null);
  const genId = pickedGenId === undefined ? (session?.photos?.id ?? null) : pickedGenId;
  const credits = polledCredits ?? session?.credits ?? null;
  const [paywall, setPaywall] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [madeShare, setMadeShare] = useState<ShareView | null>(null);
  const share = madeShare ?? (genId && session?.photos?.id === genId ? session?.share ?? null : null);
  const [slides, setSlides] = useState<string[] | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (session === null) router.replace("/");
    if (session && (!session.face || session.face.status !== "done")) router.replace("/face");
  }, [session, router]);

  const { gen, error: pollError } = usePollGeneration(genId, (_g: GenerationView, c) => c && setCredits(c));
  const photosPerSet = session?.policy.photosPerSet ?? 4;

  const generate = async () => {
    setBusy(true);
    setErr("");
    setMadeShare(null);
    setSlides(null);
    const res = await fetch("/api/generate/photos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ place, mood }),
    });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (res.status === 402) return setPaywall(true);
    if (!res.ok) return setErr(data.error ?? "생성을 시작하지 못했어요.");
    await reload();
    router.replace(`/photos?g=${data.generation.id}`);
    setGenId(data.generation.id);
  };

  const makeShare = async () => {
    setBusy(true);
    setErr("");
    const res = await fetch("/api/share", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (!res.ok) return setErr(data.error ?? "공유 카드를 만들지 못했어요.");
    const fresh = await reload();
    setMadeShare(fresh?.share ?? { ...data.share, question: "", choices: [], tally: {}, total: 0 });
    const s = await fetch(data.share.storyUrl).then((r) => r.json()).catch(() => null);
    if (s?.slides) setSlides(s.slides);
  };

  const loadSlides = async () => {
    if (!share) return;
    const s = await fetch(share.storyUrl).then((r) => r.json()).catch(() => null);
    if (s?.slides) setSlides(s.slides);
  };

  const copy = async () => {
    if (!share) return;
    try {
      if (navigator.share) {
        await navigator.share({ title: `${share.question || "성형 후 내 모습"} · 애프터`, text: share.question ? `${share.question} 링크에서 투표해 줘!` : undefined, url: share.url });
        return;
      }
      await navigator.clipboard.writeText(share.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* 사용자가 취소 */
    }
  };

  const showPicker = !genId || gen?.status === "failed" || !!pollError;
  const loading = genId && !pollError && (!gen || (gen.status !== "done" && gen.status !== "failed"));
  const done = gen?.status === "done";
  const placeLabel = gen ? PLACES[gen.params.place as PlaceId]?.label : "";
  const moodLabel = gen ? MOODS[gen.params.mood as MoodId]?.label : "";

  return (
    <Shell step="3 / 3 인생샷">
      <DisclaimerBanner />

      {showPicker ? (
        <>
          <section>
            <h1 className="text-2xl font-bold tracking-tight">어디서 찍을까요?</h1>
            <p className="mt-1 text-sm text-muted">성형 후 얼굴로 {photosPerSet}장을 만들어요. 얼굴 동일성을 최우선으로 유지해요.</p>
          </section>
          {gen?.status === "failed" ? (
            <p className="rounded-xl bg-accent-soft px-3 py-2 text-xs">이전 생성에 실패했어요: {gen.error}. 크레딧은 돌려드렸어요.</p>
          ) : null}
          {pollError ? <p className="rounded-xl bg-accent-soft px-3 py-2 text-xs">{pollError}</p> : null}
          <div>
            <h2 className="mb-2 text-sm font-semibold">장소</h2>
            <div className="grid grid-cols-3 gap-2">
              {PLACE_IDS.map((id) => (
                <button key={id} onClick={() => setPlace(id)} className={`card flex flex-col items-center gap-1 py-3 transition ${place === id ? "border-ink ring-1 ring-ink" : ""}`}>
                  <span className="text-2xl">{PLACES[id].emoji}</span>
                  <span className="text-xs font-semibold">{PLACES[id].label}</span>
                </button>
              ))}
            </div>
          </div>
          <div>
            <h2 className="mb-2 text-sm font-semibold">분위기</h2>
            <div className="flex gap-2">
              {MOOD_IDS.map((id) => (
                <button key={id} onClick={() => setMood(id)} className={`chip flex-1 py-2.5 ${mood === id ? "chip-on" : ""}`}>
                  {MOODS[id].label}
                </button>
              ))}
            </div>
          </div>
          {err ? <p className="text-sm font-medium text-accent">{err}</p> : null}
          <button onClick={generate} disabled={busy} className="btn btn-accent">
            {busy ? "시작하는 중…" : `인생샷 ${photosPerSet}장 만들기`}
          </button>
          <p className="text-center text-xs text-muted">남은 무료 인생샷 {credits?.photo ?? "-"}장</p>
        </>
      ) : null}

      {loading ? <LoadingSteps kind="photo" stage={gen?.status ?? "queued"} /> : null}

      {done && gen ? (
        <>
          <section>
            <h1 className="text-2xl font-bold tracking-tight">인생샷 {gen.outputs.length}장</h1>
            <p className="mt-1 text-sm text-muted">
              {placeLabel} · {moodLabel}
              {gen.params.variantLabel ? ` · ${String(gen.params.variantLabel)} 강도 얼굴` : ""}
            </p>
          </section>
          <div className="grid grid-cols-2 gap-2">
            {gen.outputs.map((u, i) => (
              <a key={u} href={u} target="_blank" rel="noreferrer" className="overflow-hidden rounded-xl bg-surface" style={{ aspectRatio: "4 / 5" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={u} alt={`인생샷 ${i + 1}`} className="h-full w-full object-cover" />
              </a>
            ))}
          </div>
          <p className="text-center text-xs text-muted">사진을 누르면 원본 크기로 열려요. 길게 눌러 저장하세요.</p>

          {!share ? (
            <button onClick={makeShare} disabled={busy} className="btn btn-accent">
              {busy ? "공유 카드 만드는 중…" : "친구한테 물어보기 (공유 링크 만들기)"}
            </button>
          ) : (
            <div className="card flex flex-col gap-3">
              {share.choices.length ? (
                <VoteTally question={share.question} choices={share.choices} tally={share.tally} total={share.total} onRefresh={() => reload()} />
              ) : null}
              <p className="text-sm font-semibold">공유 링크</p>
              <div className="flex items-center gap-2 rounded-xl bg-surface px-3 py-2 text-xs">
                <span className="flex-1 truncate">{share.url}</span>
                <button onClick={copy} className="rounded-lg bg-ink px-3 py-1.5 font-semibold text-white">
                  {copied ? "복사됨" : "공유"}
                </button>
              </div>
              <p className="text-xs text-muted">공유 페이지에는 성형 후 얼굴과 인생샷만 보여요. 원본 사진은 절대 노출되지 않아요. 친구들은 로그인 없이 투표할 수 있고, 링크는 7일 뒤 만료돼요.</p>
              <p className="pt-1 text-sm font-semibold">인스타 스토리용 카드 (1080×1920)</p>
              {slides ? (
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {slides.map((s, i) => (
                    <a key={s} href={s} download={`after-story-${i + 1}.jpg`} target="_blank" rel="noreferrer" className="w-24 shrink-0 overflow-hidden rounded-lg bg-surface" style={{ aspectRatio: "9 / 16" }}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={s} alt={`스토리 ${i + 1}`} className="h-full w-full object-cover" />
                    </a>
                  ))}
                </div>
              ) : (
                <button onClick={loadSlides} className="rounded-xl border border-line py-2 text-sm">스토리 카드 불러오기</button>
              )}
              <p className="text-xs text-muted">비포/애프터가 들어간 카드는 나에게만 보여요. 저장해서 직접 올리세요.</p>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <button
              onClick={() => {
                setGenId(null);
                setMadeShare(null);
                router.replace("/photos");
              }}
              className="btn btn-secondary"
            >
              다른 장소로 다시 만들기 (남은 {credits?.photo ?? 0}장)
            </button>
            <Link href="/face" className="py-2 text-center text-sm text-muted underline underline-offset-2">
              얼굴 결과로 돌아가기
            </Link>
          </div>
          {err ? <p className="text-sm font-medium text-accent">{err}</p> : null}
          <div className="flex justify-center">
            <DeleteDataButton />
          </div>
        </>
      ) : null}
      <PaywallModal open={paywall} onClose={() => setPaywall(false)} kind="photo" />
    </Shell>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Photos />
    </Suspense>
  );
}
