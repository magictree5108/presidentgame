import type { Store } from "./types";

/**
 * 저장소 선택.
 *   STORE_DRIVER = "supabase" | "local"
 *   기본: Supabase 키가 있으면 supabase, 없으면 local (개발 전용)
 */
export function storeDriver(): "supabase" | "local" {
  const explicit = process.env.STORE_DRIVER;
  if (explicit === "supabase" || explicit === "local") return explicit;
  return process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY ? "supabase" : "local";
}

const g = globalThis as unknown as { __afterStore?: Store };

export async function getStore(): Promise<Store> {
  if (g.__afterStore) return g.__afterStore;
  if (storeDriver() === "supabase") {
    const { SupabaseStore } = await import("./supabase");
    g.__afterStore = new SupabaseStore();
  } else {
    if (process.env.NODE_ENV === "production" && process.env.ALLOW_LOCAL_STORE_IN_PROD !== "1") {
      throw new Error("프로덕션에서 로컬 저장소를 쓸 수 없습니다. Supabase 환경변수를 설정하세요.");
    }
    const { LocalStore } = await import("./local");
    g.__afterStore = new LocalStore();
  }
  return g.__afterStore;
}

export type * from "./types";
