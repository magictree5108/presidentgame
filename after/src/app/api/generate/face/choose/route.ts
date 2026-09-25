import { z } from "zod";
import { jsonError, requireSession } from "@/lib/session";
import { chooseFaceVariant, publicGeneration } from "@/lib/generation";

const Body = z.object({ index: z.number().int().min(0).max(9) });

/** 강도 비교 결과 중 하나를 "내 애프터"로 고른다. 인생샷과 공유는 이 선택을 쓴다. */
export async function POST(req: Request) {
  try {
    const session = await requireSession();
    const parsed = Body.safeParse(await req.json().catch(() => null));
    if (!parsed.success) return Response.json({ error: "선택값이 올바르지 않아요." }, { status: 400 });
    const gen = await chooseFaceVariant(session, parsed.data.index);
    return Response.json({ generation: await publicGeneration(gen) });
  } catch (e) {
    return jsonError(e);
  }
}
