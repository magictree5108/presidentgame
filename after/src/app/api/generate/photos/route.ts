import { z } from "zod";
import { jsonError, requireSession } from "@/lib/session";
import { publicGeneration, startPhotoGeneration } from "@/lib/generation";
import { MOOD_IDS, PLACE_IDS } from "../../../../../prompts/lifeshot";

const Body = z.object({ place: z.enum(PLACE_IDS), mood: z.enum(MOOD_IDS) });

export async function POST(req: Request) {
  try {
    const session = await requireSession();
    const parsed = Body.safeParse(await req.json().catch(() => null));
    if (!parsed.success) return Response.json({ error: "장소와 분위기를 골라 주세요." }, { status: 400 });
    const gen = await startPhotoGeneration(session, parsed.data.place, parsed.data.mood);
    return Response.json({ generation: await publicGeneration(gen) });
  } catch (e) {
    return jsonError(e);
  }
}
