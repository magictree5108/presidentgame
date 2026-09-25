import { jsonError, requireSession, HttpError } from "@/lib/session";
import { getStore } from "@/lib/store";
import { publicGeneration, refreshGeneration } from "@/lib/generation";

/** 생성 상태 폴링. 끝났으면 이 요청 안에서 결과를 처리해 저장한다. */
export async function GET(_req: Request, ctx: RouteContext<"/api/generations/[id]">) {
  try {
    const session = await requireSession();
    const { id } = await ctx.params;
    const store = await getStore();
    const gen = await store.getGeneration(id);
    if (!gen || gen.sessionId !== session.id) throw new HttpError(404, "생성 기록을 찾을 수 없어요.");
    const fresh = await refreshGeneration(gen);
    const s = await store.getSession(session.id);
    return Response.json({
      generation: await publicGeneration(fresh),
      credits: s ? { face: s.faceCredits, photo: s.photoCredits } : null,
    });
  } catch (e) {
    return jsonError(e);
  }
}
