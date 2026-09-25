import { jsonError, requireSession, HttpError } from "@/lib/session";
import { getStore } from "@/lib/store";

/** 스토리 슬라이드 다운로드 링크. 본인 세션만. 서명 URL 10분. */
export async function GET(_req: Request, ctx: RouteContext<"/api/share/[id]/story">) {
  try {
    const session = await requireSession();
    const { id } = await ctx.params;
    const store = await getStore();
    const share = await store.getShare(id);
    if (!share || share.sessionId !== session.id) throw new HttpError(404, "공유 카드를 찾을 수 없어요.");
    const slides = await Promise.all(share.storyPaths.map((p) => store.signedUrl("private", p, 600)));
    return Response.json({ slides });
  } catch (e) {
    return jsonError(e);
  }
}
