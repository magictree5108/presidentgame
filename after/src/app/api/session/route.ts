import { z } from "zod";
import { currentSession, jsonError, startSession } from "@/lib/session";
import { getStore } from "@/lib/store";
import { publicGeneration } from "@/lib/generation";
import { providerInfo } from "@/lib/providers";
import { POLICY } from "@/lib/config";

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
    return Response.json({
      session: {
        id: session.id,
        credits: { face: session.faceCredits, photo: session.photoCredits },
        policy: { photosPerSet: POLICY.photosPerSet },
        uploads: uploads.map((u) => ({ id: u.id, kind: u.kind, url: `/api/uploads/${u.id}` })),
        selection: session.selection,
        face: face ? await publicGeneration(face) : null,
        photos: photos ? await publicGeneration(photos) : null,
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
    return Response.json({ ok: true, credits: { face: session.faceCredits, photo: session.photoCredits } });
  } catch (e) {
    return jsonError(e);
  }
}
