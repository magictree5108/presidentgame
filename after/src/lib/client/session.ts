"use client";
import { useCallback, useEffect, useState } from "react";

/** /api/session 응답 형태 (클라이언트용) */
export type GenerationView = {
  id: string;
  kind: "face" | "photo";
  status: "queued" | "running" | "processing" | "done" | "failed";
  error: string | null;
  params: Record<string, unknown>;
  outputs: string[];
  createdAt: string;
};

export type SessionView = {
  id: string;
  credits: { face: number; photo: number };
  policy: { photosPerSet: number };
  uploads: Array<{ id: string; kind: "front" | "side"; url: string }>;
  selection: unknown | null;
  face: GenerationView | null;
  photos: GenerationView | null;
  provider: { provider: string; face: string; photo: string };
};

export function useSession() {
  const [session, setSession] = useState<SessionView | null | undefined>(undefined);
  const reload = useCallback(async () => {
    const res = await fetch("/api/session", { cache: "no-store" });
    const data = await res.json();
    setSession(data.session ?? null);
    return (data.session ?? null) as SessionView | null;
  }, []);
  useEffect(() => {
    let alive = true;
    fetch("/api/session", { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => alive && setSession(data.session ?? null))
      .catch(() => alive && setSession(null));
    return () => {
      alive = false;
    };
  }, []);
  return { session, reload, setSession };
}

/** 생성 상태를 done/failed 가 될 때까지 폴링한다. */
export function usePollGeneration(
  id: string | null,
  onUpdate?: (g: GenerationView, credits: { face: number; photo: number } | null) => void,
) {
  const [gen, setGen] = useState<GenerationView | null>(null);
  useEffect(() => {
    if (!id) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const res = await fetch(`/api/generations/${id}`, { cache: "no-store" });
        const data = await res.json();
        if (stop) return;
        if (data.generation) {
          setGen(data.generation);
          onUpdate?.(data.generation, data.credits ?? null);
          if (data.generation.status === "done" || data.generation.status === "failed") return;
        }
      } catch {
        // 네트워크 오류는 다음 틱에서 재시도
      }
      timer = setTimeout(tick, 2500);
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  return gen;
}
