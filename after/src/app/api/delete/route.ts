import { jsonError, requireSession } from "@/lib/session";
import { getStore } from "@/lib/store";

/** 내 데이터 즉시 삭제. 원본, 생성물, 공유 카드 전부. 크레딧은 유지된다. */
export async function POST() {
  try {
    const session = await requireSession();
    const store = await getStore();
    const report = await store.deleteSessionData(session.id);
    await store.logEvent({ sessionId: session.id, name: "data_deleted", props: report as unknown as Record<string, unknown> });
    return Response.json({ ok: true, report });
  } catch (e) {
    return jsonError(e);
  }
}
