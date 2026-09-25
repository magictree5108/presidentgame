import { z } from "zod";
import { currentSessionId, jsonError } from "@/lib/session";
import { getStore } from "@/lib/store";

const Body = z.object({ email: z.string().trim().toLowerCase().email().max(200) });

export async function POST(req: Request) {
  try {
    const parsed = Body.safeParse(await req.json().catch(() => null));
    if (!parsed.success) return Response.json({ error: "이메일 형식을 확인해 주세요." }, { status: 400 });
    const store = await getStore();
    await store.addToWaitlist(parsed.data.email, await currentSessionId());
    return Response.json({ ok: true });
  } catch (e) {
    return jsonError(e);
  }
}
