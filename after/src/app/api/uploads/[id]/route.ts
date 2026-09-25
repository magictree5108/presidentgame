import { jsonError, requireSession, HttpError } from "@/lib/session";
import { getStore } from "@/lib/store";

/** 업로더 본인만 볼 수 있는 원본 미리보기. 짧은 서명 URL 로 리다이렉트한다. */
export async function GET(_req: Request, ctx: RouteContext<"/api/uploads/[id]">) {
  try {
    const session = await requireSession();
    const { id } = await ctx.params;
    const store = await getStore();
    const up = await store.getUpload(id);
    if (!up || up.sessionId !== session.id) throw new HttpError(404, "사진을 찾을 수 없어요.");
    const url = await store.signedUrl("private", up.path, 60 * 10);
    return Response.redirect(url, 302);
  } catch (e) {
    return jsonError(e);
  }
}
