import crypto from "node:crypto";
import { getStore } from "@/lib/store";

/**
 * 만료 데이터 정리. Supabase pg_cron(또는 Vercel Cron)이 호출한다.
 * Authorization: Bearer <CRON_SECRET> 가 있어야 한다.
 */
async function run(req: Request) {
  const secret = process.env.CRON_SECRET;
  const auth = req.headers.get("authorization") ?? "";
  const expected = `Bearer ${secret}`;
  const ok = !!secret && auth.length === expected.length && crypto.timingSafeEqual(Buffer.from(auth), Buffer.from(expected));
  if (!ok) return Response.json({ error: "unauthorized" }, { status: 401 });
  const store = await getStore();
  const report = await store.cleanupExpired(new Date());
  return Response.json({ ok: true, report });
}

export const GET = run;
export const POST = run;
