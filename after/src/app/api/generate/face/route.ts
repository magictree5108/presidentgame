import { z } from "zod";
import { jsonError, requireSession } from "@/lib/session";
import { publicGeneration, startFaceGeneration } from "@/lib/generation";
import { INTENSITIES, SURGERY_PARTS, type SurgerySelection } from "../../../../../prompts/surgery";

const PartSchema = z.object({ enabled: z.boolean(), intensity: z.enum(INTENSITIES) });
const Body = z.object({
  selection: z.object(Object.fromEntries(SURGERY_PARTS.map((p) => [p, PartSchema])) as Record<(typeof SURGERY_PARTS)[number], typeof PartSchema>),
});

export async function POST(req: Request) {
  try {
    const session = await requireSession();
    const parsed = Body.safeParse(await req.json().catch(() => null));
    if (!parsed.success) return Response.json({ error: "선택값이 올바르지 않아요." }, { status: 400 });
    const selection = parsed.data.selection as SurgerySelection;
    if (!SURGERY_PARTS.some((p) => selection[p].enabled)) {
      return Response.json({ error: "바꿀 부위를 하나 이상 골라 주세요." }, { status: 400 });
    }
    const gen = await startFaceGeneration(session, selection);
    return Response.json({ generation: await publicGeneration(gen) });
  } catch (e) {
    return jsonError(e);
  }
}
