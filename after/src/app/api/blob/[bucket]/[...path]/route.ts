import { storeDriver, getStore } from "@/lib/store";
import { verifyLocalSignature } from "@/lib/store/local";

/**
 * 로컬 저장소 전용 파일 서빙. Supabase 모드에서는 404.
 *  - public 버킷: 누구나
 *  - private 버킷: exp/sig 서명이 있어야 함
 */
export async function GET(req: Request, ctx: RouteContext<"/api/blob/[bucket]/[...path]">) {
  if (storeDriver() !== "local") return new Response("not found", { status: 404 });
  const { bucket, path } = await ctx.params;
  if (bucket !== "public" && bucket !== "private") return new Response("not found", { status: 404 });
  const p = path.join("/");
  if (bucket === "private") {
    const url = new URL(req.url);
    const exp = Number(url.searchParams.get("exp"));
    const sig = url.searchParams.get("sig") ?? "";
    if (!exp || !verifyLocalSignature(bucket, p, exp, sig)) return new Response("forbidden", { status: 403 });
  }
  const store = await getStore();
  const buf = await store.getBlob(bucket, p);
  if (!buf) return new Response("not found", { status: 404 });
  return new Response(new Uint8Array(buf), {
    headers: {
      "Content-Type": p.endsWith(".png") ? "image/png" : "image/jpeg",
      "Cache-Control": bucket === "public" ? "public, max-age=3600" : "private, no-store",
    },
  });
}
