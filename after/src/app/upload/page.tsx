"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Shell } from "@/components/Shell";
import { useSession } from "@/lib/client/session";
import { checkFace } from "@/lib/client/face-detect";
import { POLICY } from "@/lib/config";

type Picked = { file: File; url: string; status: "checking" | "ok" | "bad"; reason?: string };

export default function UploadPage() {
  const router = useRouter();
  const { session } = useSession();
  const [front, setFront] = useState<Picked | null>(null);
  const [sides, setSides] = useState<Picked[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const camRef = useRef<HTMLInputElement>(null);
  const galRef = useRef<HTMLInputElement>(null);
  const sideRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (session === null) router.replace("/");
  }, [session, router]);

  const pick = async (file: File): Promise<Picked> => {
    const p: Picked = { file, url: URL.createObjectURL(file), status: "checking" };
    const r = await checkFace(file);
    return r.ok ? { ...p, status: "ok" } : { ...p, status: "bad", reason: r.reason };
  };

  const onFront = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setErr("");
    setFront({ file: f, url: URL.createObjectURL(f), status: "checking" });
    setFront(await pick(f));
  };

  const onSides = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).slice(0, POLICY.maxSidePhotos - sides.length);
    e.target.value = "";
    if (!files.length) return;
    const picked = await Promise.all(files.map(pick));
    setSides((s) => [...s, ...picked].slice(0, POLICY.maxSidePhotos));
  };

  const canSubmit = front?.status === "ok" && sides.every((s) => s.status === "ok") && !busy;

  const submit = async () => {
    if (!front || front.status !== "ok") return;
    setBusy(true);
    setErr("");
    const fd = new FormData();
    fd.append("front", front.file);
    for (const s of sides) fd.append("side", s.file);
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (!res.ok) return setErr(data.error ?? "업로드에 실패했어요.");
    router.push("/select");
  };

  return (
    <Shell step="1 / 3 사진">
      <section>
        <h1 className="text-2xl font-bold tracking-tight">정면 셀카 한 장</h1>
        <p className="mt-1 text-sm text-muted">밝은 곳에서, 안경과 앞머리는 치우고, 무표정이나 살짝 미소가 가장 잘 나와요.</p>
      </section>

      {/* 모바일: 카메라 촬영이 기본, 갤러리는 부차 옵션 */}
      <input ref={camRef} type="file" accept="image/*" capture="user" className="hidden" onChange={onFront} />
      <input ref={galRef} type="file" accept="image/*" className="hidden" onChange={onFront} />
      <input ref={sideRef} type="file" accept="image/*" multiple className="hidden" onChange={onSides} />

      <div className="card flex flex-col items-center gap-3">
        {front ? (
          <div className="relative w-full overflow-hidden rounded-xl bg-surface" style={{ aspectRatio: "3 / 4" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={front.url} alt="정면 사진 미리보기" className="h-full w-full object-cover" />
            <Status p={front} />
          </div>
        ) : (
          <div className="flex w-full flex-col items-center justify-center rounded-xl bg-surface text-sm text-muted" style={{ aspectRatio: "3 / 4" }}>
            <span className="text-4xl">🤳</span>
            <span className="mt-2">정면 셀카가 여기에 보여요</span>
          </div>
        )}
        <button onClick={() => camRef.current?.click()} className="btn btn-primary">
          {front ? "다시 촬영" : "카메라로 촬영"}
        </button>
        <button onClick={() => galRef.current?.click()} className="w-full py-1 text-sm text-muted underline underline-offset-2">
          갤러리에서 고르기
        </button>
      </div>

      <section className="card">
        <div className="flex items-baseline justify-between">
          <h2 className="font-semibold">측면 사진 (선택, 최대 {POLICY.maxSidePhotos}장)</h2>
          <span className="text-xs text-muted">인생샷 얼굴 일치도가 올라가요</span>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {sides.map((s, i) => (
            <div key={s.url} className="relative overflow-hidden rounded-lg bg-surface" style={{ aspectRatio: "3 / 4" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={s.url} alt={`측면 ${i + 1}`} className="h-full w-full object-cover" />
              <Status p={s} small />
              <button
                onClick={() => setSides((arr) => arr.filter((_, k) => k !== i))}
                className="absolute top-1 right-1 rounded-full bg-black/60 px-2 py-0.5 text-xs text-white"
                aria-label="삭제"
              >
                ✕
              </button>
            </div>
          ))}
          {sides.length < POLICY.maxSidePhotos ? (
            <button onClick={() => sideRef.current?.click()} className="flex items-center justify-center rounded-lg border border-dashed border-line text-2xl text-muted" style={{ aspectRatio: "3 / 4" }}>
              +
            </button>
          ) : null}
        </div>
      </section>

      {err ? <p className="text-sm font-medium text-accent">{err}</p> : null}
      <button onClick={submit} disabled={!canSubmit} className="btn btn-accent">
        {busy ? "올리는 중…" : "다음: 부위 고르기"}
      </button>
      <p className="text-center text-xs text-muted">얼굴 감지는 내 기기에서 처리돼요. 원본은 24시간 뒤 자동 삭제돼요.</p>
    </Shell>
  );
}

function Status({ p, small }: { p: Picked; small?: boolean }) {
  const cls = `absolute right-2 bottom-2 left-2 rounded-lg px-2 py-1 text-center font-medium text-white ${small ? "text-[10px]" : "text-xs"}`;
  if (p.status === "checking") return <span className={`${cls} bg-black/60`}>얼굴 확인 중…</span>;
  if (p.status === "bad") return <span className={`${cls} bg-accent`}>{p.reason}</span>;
  return <span className={`${cls} bg-emerald-600`}>얼굴 1명 확인</span>;
}
