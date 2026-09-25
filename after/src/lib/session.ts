import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import { storeDriver, getStore } from "@/lib/store";
import type { Session } from "@/lib/store";
import { POLICY } from "@/lib/config";
import crypto from "node:crypto";

/**
 * 익명 세션.
 *  - supabase 드라이버: Supabase Anonymous Sign-in. 서버가 로그인하고 @supabase/ssr 이 쿠키를 관리한다.
 *    세션 ID = auth user id. (대시보드 Authentication > Providers > Anonymous sign-ins 를 켜야 한다)
 *  - local 드라이버: httpOnly 쿠키에 UUID 를 넣는다.
 */

const LOCAL_COOKIE = "after_sid";

async function supabaseServerClient() {
  const cookieStore = await cookies();
  return createServerClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: (list) => {
        try {
          for (const { name, value, options } of list) cookieStore.set(name, value, options);
        } catch {
          // 서버 컴포넌트에서 호출되면 쿠키를 쓸 수 없다. 라우트 핸들러에서만 갱신된다.
        }
      },
    },
  });
}

/** 현재 요청의 세션 ID. 없으면 null. */
export async function currentSessionId(): Promise<string | null> {
  if (storeDriver() === "supabase") {
    const sb = await supabaseServerClient();
    const { data } = await sb.auth.getUser();
    return data.user?.id ?? null;
  }
  const c = await cookies();
  return c.get(LOCAL_COOKIE)?.value ?? null;
}

/** 세션 ID 를 새로 만든다 (로그인/쿠키 발급). */
async function issueSessionId(): Promise<string> {
  if (storeDriver() === "supabase") {
    const sb = await supabaseServerClient();
    const existing = await sb.auth.getUser();
    if (existing.data.user) return existing.data.user.id;
    const { data, error } = await sb.auth.signInAnonymously();
    if (error || !data.user) throw new Error(`익명 로그인 실패: ${error?.message ?? "unknown"}. Supabase 에서 Anonymous sign-ins 를 켰는지 확인하세요.`);
    return data.user.id;
  }
  const c = await cookies();
  const id = crypto.randomUUID();
  c.set(LOCAL_COOKIE, id, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return id;
}

/** 현재 세션 행. 없으면 null. */
export async function currentSession(): Promise<Session | null> {
  const id = await currentSessionId();
  if (!id) return null;
  const store = await getStore();
  return store.getSession(id);
}

/** 랜딩에서 두 체크박스를 모두 체크했을 때 호출. 세션을 만들고 무료 크레딧을 준다. 이미 있으면 그대로 돌려준다. */
export async function startSession(): Promise<Session> {
  const store = await getStore();
  const existingId = await currentSessionId();
  if (existingId) {
    const existing = await store.getSession(existingId);
    if (existing) return existing;
  }
  const id = existingId ?? (await issueSessionId());
  const nowIso = new Date().toISOString();
  return store.createSession(id, {
    ageConfirmedAt: nowIso,
    consentAt: nowIso,
    faceCredits: POLICY.freeCredits.face,
    photoCredits: POLICY.freeCredits.photo,
  });
}

export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
    public extra?: Record<string, unknown>,
  ) {
    super(message);
  }
}

/** 라우트 핸들러용: 세션이 없으면 401. */
export async function requireSession(): Promise<Session> {
  const s = await currentSession();
  if (!s) throw new HttpError(401, "세션이 없어요. 처음부터 다시 시작해 주세요.");
  return s;
}

export function jsonError(e: unknown): Response {
  if (e instanceof HttpError) {
    return Response.json({ error: e.message, ...(e.extra ?? {}) }, { status: e.status });
  }
  // 내부 오류 메시지(테이블·버킷·프로바이더 세부)는 서버 로그에만 남기고 클라이언트에는 일반 문구만 준다.
  console.error(e);
  return Response.json({ error: "서버 오류가 발생했어요. 잠시 후 다시 시도해 주세요." }, { status: 500 });
}
