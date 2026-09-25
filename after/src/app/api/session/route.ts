import { z } from "zod";
import { currentSession, jsonError, startSession } from "@/lib/session";
import { getStore } from "@/lib/store";
import { publicGeneration } from "@/lib/generation";
import { providerInfo } from "@/lib/providers";
import { POLICY } from "@/lib/config";
import { appUrl } from "@/lib/brand";
import { voteChoices, voteQuestion } from "@/lib/vote";

/** 세션 상태 요약. 각 화면이 진입할 때 호출한다. */
export async function GET() {
  try {
    const session = await currentSession();
    if (!session) return Response.json({ session: null });
    const store = await getStore();
    const [uploads, face, photos] = await Promise.all([
      store.listUploads(session.id),
      session.currentFaceGenerationId ? store.getGeneration(session.currentFaceGenerationId) : null,
      session.currentPhotoGenerationId ? store.getGeneration(session.currentPhotoGenerationId) : null,
    ]);
    // 현재 얼굴+인생샷 조합으로 만든 공유가 있으면 투표 현황과 함께 내려준다.
    let share = null;
    if (face && photos) {
      const existing = (await store.listShares(session.id)).find((s) => s.faceGenerationId === face.id && s.photoGenerationId === photos.id);
      if (existing) {
        const tally = await store.getVoteTally(existing.id);
        share = {
          id: existing.id,
          url: `${appUrl()}/s/${existing.id}`,
          storyUrl: `/api/share/${existing.id}/story`,
          question: voteQuestion(existing.variantLabels.length),
          choices: voteChoices(existing.variantLabels),
          tally,
          total: Object.values(tally).reduce((a, b) => a + b, 0),
        };
      }
    }
    return Response.json({
      session: {
        id: session.id,
        credits: { face: session.faceCredits, photo: session.photoCredits },
        policy: { photosPerSet: POLICY.photosPerSet },
        uploads: uploads.map((u) => ({ id: u.id, kind: u.kind, url: `/api/uploads/${u.id}` })),
        selection: session.selection,
        face: face ? await publicGeneration(face) : null,
        photos: photos ? await publicGeneration(photos) : null,
        share,
        provider: providerInfo(),
      },
    });
  } catch (e) {
    return jsonError(e);
  }
}

const Body = z.object({ ageConfirmed: z.literal(true), faceConsent: z.literal(true) });

/** 랜딩에서 두 체크박스를 모두 체크하고 시작을 눌렀을 때. */
export async function POST(req: Request) {
  try {
    const parsed = Body.safeParse(await req.json().catch(() => ({})));
    if (!parsed.success) return Response.json({ error: "만 19세 이상 확인과 얼굴 데이터 처리 동의가 모두 필요해요." }, { status: 400 });
    const session = await startSession();
    const store = await getStore();
    await store.logEvent({ sessionId: session.id, name: "session_started", props: {} });
    return Response.json({ ok: true, credits: { face: session.faceCredits, photo: session.photoCredits } });
  } catch (e) {
    return jsonError(e);
  }
}
