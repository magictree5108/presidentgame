import crypto from "node:crypto";
import { cookies } from "next/headers";
import { z } from "zod";
import { getStore } from "@/lib/store";
import { currentSessionId, jsonError } from "@/lib/session";
import { isValidChoice, voteChoices, voteQuestion } from "@/lib/vote";

/**
 * 공유 페이지 투표. 로그인 없이 누구나. 방문자 식별은 httpOnly 쿠키(after_voter).
 * GET: 내 표 + (이미 투표했거나 주인일 때만) 집계
 * POST: 투표/변경
 */
const VOTER_COOKIE = "after_voter";
const Body = z.object({ choice: z.string().min(1).max(20) });

async function voterKey(create: boolean): Promise<string | null> {
  const c = await cookies();
  const existing = c.get(VOTER_COOKIE)?.value;
  if (existing || !create) return existing ?? null;
  const key = crypto.randomUUID();
  c.set(VOTER_COOKIE, key, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 60 * 60 * 24 * 365 });
  return key;
}

async function view(shareId: string, key: string | null, reveal: boolean) {
  const store = await getStore();
  const share = await store.getShare(shareId);
  if (!share) return Response.json({ error: "공유를 찾을 수 없어요." }, { status: 404 });
  const mine = key ? await store.getVote(shareId, key) : null;
  const sessionId = await currentSessionId();
  const isOwner = sessionId === share.sessionId;
  const showTally = reveal || isOwner || !!mine;
  const tally = showTally ? await store.getVoteTally(shareId) : null;
  return Response.json({
    question: voteQuestion(share.variantLabels.length),
    choices: voteChoices(share.variantLabels),
    mine,
    isOwner,
    tally,
    total: tally ? Object.values(tally).reduce((a, b) => a + b, 0) : null,
  });
}

export async function GET(_req: Request, ctx: RouteContext<"/api/share/[id]/vote">) {
  try {
    const { id } = await ctx.params;
    return view(id, await voterKey(false), false);
  } catch (e) {
    return jsonError(e);
  }
}

export async function POST(req: Request, ctx: RouteContext<"/api/share/[id]/vote">) {
  try {
    const { id } = await ctx.params;
    const parsed = Body.safeParse(await req.json().catch(() => null));
    if (!parsed.success) return Response.json({ error: "선택값이 올바르지 않아요." }, { status: 400 });
    const store = await getStore();
    const share = await store.getShare(id);
    if (!share) return Response.json({ error: "공유를 찾을 수 없어요." }, { status: 404 });
    if (!isValidChoice(share.variantLabels, parsed.data.choice)) return Response.json({ error: "없는 선택지예요." }, { status: 400 });
    const key = (await voterKey(true))!;
    await store.castVote(id, key, parsed.data.choice);
    await store.logEvent({ sessionId: await currentSessionId(), name: "vote_cast", props: { shareId: id, choice: parsed.data.choice } });
    return view(id, key, true);
  } catch (e) {
    return jsonError(e);
  }
}
