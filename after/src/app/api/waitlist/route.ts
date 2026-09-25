import { z } from "zod";
import { currentSessionId, jsonError } from "@/lib/session";
import { getStore } from "@/lib/store";

const Body = z.object({ email: z.string().trim().toLowerCase().email().max(200) });

export async function POST(req: Request) {
  try {
    const parsed = Body.safeParse(await req.json().catch(() => null));
    if (!parsed.success) return Response.json({ error: "이메일 형식을 확인해 주세요." }, { status: 400 });
    const store = await getStore();
    const sessionId = await currentSessionId();
    await store.addToWaitlist(parsed.data.email, sessionId);
    await store.logEvent({ sessionId, name: "waitlist_joined", props: {} });
    return Response.json({ ok: true });
  } catch (e) {
    return jsonError(e);
  }
}
