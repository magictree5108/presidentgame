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
  chosen: number | null;
  createdAt: string;
};

export type VoteChoiceView = { id: string; label: string; emoji: string };
export type ShareView = {
  id: string;
  url: string;
  storyUrl: string;
  question: string;
  choices: VoteChoiceView[];
  tally: Record<string, number>;
  total: number;
};

export type SessionView = {
  id: string;
  credits: { face: number; photo: number };
  policy: { photosPerSet: number };
  uploads: Array<{ id: string; kind: "front" | "side"; url: string }>;
  selection: unknown | null;
  face: GenerationView | null;
  photos: GenerationView | null;
  share: ShareView | null;
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
): { gen: GenerationView | null; error: string | null } {
  const [gen, setGen] = useState<GenerationView | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!id) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    let netFailures = 0;
    const tick = async () => {
      try {
        const res = await fetch(`/api/generations/${id}`, { cache: "no-store" });
        const data = await res.json();
        if (stop) return;
        if (data.generation) {
          netFailures = 0;
          setGen(data.generation);
          onUpdate?.(data.generation, data.credits ?? null);
          if (data.generation.status === "done" || data.generation.status === "failed") return;
        } else {
          // 401/404 등: 세션이 끝났거나 생성물이 삭제됐다. 더 폴링하지 않는다.
          setError(data.error ?? "생성 기록을 찾을 수 없어요. 처음부터 다시 시작해 주세요.");
          return;
        }
      } catch {
        // 네트워크 오류는 몇 번 재시도하고 포기한다.
        if (++netFailures >= 12) {
          setError("네트워크 연결을 확인해 주세요.");
          return;
        }
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
  return { gen, error };
}
