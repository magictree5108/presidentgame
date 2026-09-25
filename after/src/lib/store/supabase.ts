import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { CreditKind } from "@/lib/config";
import { privateGenerationPaths } from "./paths";
import type { Bucket, CleanupReport, EventRow, Generation, RateLimitResult, Session, Share, Store, Upload, VoteTally } from "./types";

/**
 * Supabase 저장소. service role 키로 서버에서만 접근한다.
 * 스키마는 supabase/migrations/0001_init.sql.
 */

let admin: SupabaseClient | null = null;
export function supabaseAdmin(): SupabaseClient {
  if (!admin) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!url || !key) throw new Error("NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 가 없습니다.");
    admin = createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
  }
  return admin;
}

type Row = Record<string, unknown>;

const sessionFromRow = (r: Row): Session => ({
  id: r.id as string,
  createdAt: r.created_at as string,
  ageConfirmedAt: (r.age_confirmed_at as string) ?? null,
  consentAt: (r.consent_at as string) ?? null,
  faceCredits: r.face_credits as number,
  photoCredits: r.photo_credits as number,
  currentUploadId: (r.current_upload_id as string) ?? null,
  currentFaceGenerationId: (r.current_face_generation_id as string) ?? null,
  currentPhotoGenerationId: (r.current_photo_generation_id as string) ?? null,
  selection: r.selection ?? null,
});
const sessionToRow = (p: Partial<Session>): Row => {
  const out: Row = {};
  if ("ageConfirmedAt" in p) out.age_confirmed_at = p.ageConfirmedAt;
  if ("consentAt" in p) out.consent_at = p.consentAt;
  if ("faceCredits" in p) out.face_credits = p.faceCredits;
  if ("photoCredits" in p) out.photo_credits = p.photoCredits;
  if ("currentUploadId" in p) out.current_upload_id = p.currentUploadId;
  if ("currentFaceGenerationId" in p) out.current_face_generation_id = p.currentFaceGenerationId;
  if ("currentPhotoGenerationId" in p) out.current_photo_generation_id = p.currentPhotoGenerationId;
  if ("selection" in p) out.selection = p.selection;
  return out;
};

const uploadFromRow = (r: Row): Upload => ({
  id: r.id as string,
  sessionId: r.session_id as string,
  kind: r.kind as Upload["kind"],
  path: r.path as string,
  width: r.width as number,
  height: r.height as number,
  createdAt: r.created_at as string,
  expiresAt: r.expires_at as string,
});

const genFromRow = (r: Row): Generation => ({
  id: r.id as string,
  sessionId: r.session_id as string,
  kind: r.kind as Generation["kind"],
  providerId: r.provider_id as string,
  externalJobId: (r.external_job_id as string) ?? null,
  status: r.status as Generation["status"],
  prompt: r.prompt as string,
  params: (r.params as Record<string, unknown>) ?? {},
  inputUploadIds: (r.input_upload_ids as string[]) ?? [],
  inputGenerationId: (r.input_generation_id as string) ?? null,
  outputPaths: (r.output_paths as string[]) ?? [],
  error: (r.error as string) ?? null,
  createdAt: r.created_at as string,
  updatedAt: r.updated_at as string,
  expiresAt: r.expires_at as string,
});
const genToRow = (p: Partial<Generation>): Row => {
  const out: Row = {};
  if ("sessionId" in p) out.session_id = p.sessionId;
  if ("kind" in p) out.kind = p.kind;
  if ("providerId" in p) out.provider_id = p.providerId;
  if ("externalJobId" in p) out.external_job_id = p.externalJobId;
  if ("status" in p) out.status = p.status;
  if ("prompt" in p) out.prompt = p.prompt;
  if ("params" in p) out.params = p.params;
  if ("inputUploadIds" in p) out.input_upload_ids = p.inputUploadIds;
  if ("inputGenerationId" in p) out.input_generation_id = p.inputGenerationId;
  if ("outputPaths" in p) out.output_paths = p.outputPaths;
  if ("error" in p) out.error = p.error;
  if ("expiresAt" in p) out.expires_at = p.expiresAt;
  out.updated_at = new Date().toISOString();
  return out;
};

const shareFromRow = (r: Row): Share => ({
  id: r.id as string,
  sessionId: r.session_id as string,
  faceGenerationId: r.face_generation_id as string,
  photoGenerationId: r.photo_generation_id as string,
  afterPath: r.after_path as string,
  variantPaths: (r.variant_paths as string[]) ?? [],
  variantLabels: (r.variant_labels as string[]) ?? [],
  chosenIndex: (r.chosen_index as number) ?? 0,
  photoPaths: (r.photo_paths as string[]) ?? [],
  ogPath: r.og_path as string,
  storyPaths: (r.story_paths as string[]) ?? [],
  caption: (r.caption as string) ?? "",
  createdAt: r.created_at as string,
  expiresAt: r.expires_at as string,
});

function must<T>(res: { data: T | null; error: { message: string } | null }, what: string): T {
  if (res.error) throw new Error(`${what}: ${res.error.message}`);
  if (res.data === null) throw new Error(`${what}: no data`);
  return res.data;
}

export class SupabaseStore implements Store {
  private db = supabaseAdmin();

  async getSession(id: string) {
    const { data, error } = await this.db.from("sessions").select("*").eq("id", id).maybeSingle();
    if (error) throw new Error(error.message);
    return data ? sessionFromRow(data) : null;
  }
  async createSession(id: string, init: { ageConfirmedAt: string; consentAt: string; faceCredits: number; photoCredits: number }) {
    const res = await this.db
      .from("sessions")
      .upsert({
        id,
        age_confirmed_at: init.ageConfirmedAt,
        consent_at: init.consentAt,
        face_credits: init.faceCredits,
        photo_credits: init.photoCredits,
      })
      .select("*")
      .single();
    return sessionFromRow(must(res, "createSession"));
  }
  async updateSession(id: string, patch: Partial<Session>) {
    const res = await this.db.from("sessions").update(sessionToRow(patch)).eq("id", id).select("*").single();
    return sessionFromRow(must(res, "updateSession"));
  }
  async consumeCredits(sessionId: string, kind: CreditKind, amount: number) {
    const { data, error } = await this.db.rpc("consume_credits", { p_session: sessionId, p_kind: kind, p_amount: amount });
    if (error) throw new Error(error.message);
    return data === true;
  }
  async refundCredits(sessionId: string, kind: CreditKind, amount: number) {
    const { error } = await this.db.rpc("refund_credits", { p_session: sessionId, p_kind: kind, p_amount: amount });
    if (error) throw new Error(error.message);
  }
  async checkRateLimit(sessionId: string, key: string, limit: number, windowSeconds: number): Promise<RateLimitResult> {
    const { data, error } = await this.db.rpc("check_rate_limit", {
      p_session: sessionId,
      p_key: key,
      p_limit: limit,
      p_window_seconds: windowSeconds,
    });
    if (error) throw new Error(error.message);
    const row = Array.isArray(data) ? data[0] : data;
    return { allowed: Boolean(row?.allowed), retryAfterSeconds: Number(row?.retry_after ?? 0) };
  }
  async createUpload(u: Omit<Upload, "id" | "createdAt">) {
    const res = await this.db
      .from("uploads")
      .insert({ session_id: u.sessionId, kind: u.kind, path: u.path, width: u.width, height: u.height, expires_at: u.expiresAt })
      .select("*")
      .single();
    return uploadFromRow(must(res, "createUpload"));
  }
  async getUpload(id: string) {
    const { data, error } = await this.db.from("uploads").select("*").eq("id", id).maybeSingle();
    if (error) throw new Error(error.message);
    return data ? uploadFromRow(data) : null;
  }
  async listUploads(sessionId: string) {
    const { data, error } = await this.db.from("uploads").select("*").eq("session_id", sessionId).order("created_at");
    if (error) throw new Error(error.message);
    return (data ?? []).map(uploadFromRow);
  }
  async deleteUploads(ids: string[]) {
    if (!ids.length) return;
    const { error } = await this.db.from("uploads").delete().in("id", ids);
    if (error) throw new Error(error.message);
  }
  async createGeneration(g: Omit<Generation, "id" | "createdAt" | "updatedAt">) {
    const res = await this.db.from("generations").insert(genToRow(g)).select("*").single();
    return genFromRow(must(res, "createGeneration"));
  }
  async getGeneration(id: string) {
    const { data, error } = await this.db.from("generations").select("*").eq("id", id).maybeSingle();
    if (error) throw new Error(error.message);
    return data ? genFromRow(data) : null;
  }
  async updateGeneration(id: string, patch: Partial<Generation>) {
    const res = await this.db.from("generations").update(genToRow(patch)).eq("id", id).select("*").single();
    return genFromRow(must(res, "updateGeneration"));
  }
  async claimGeneration(id: string, staleBefore: string) {
    const nowIso = new Date().toISOString();
    // 조건부 UPDATE 두 번: (queued|running) 또는 (processing 이면서 오래됨). 둘 다 0행이면 다른 요청이 선점한 것.
    const a = await this.db.from("generations").update({ status: "processing", updated_at: nowIso }).eq("id", id).in("status", ["queued", "running"]).select("*").maybeSingle();
    if (a.error) throw new Error(a.error.message);
    if (a.data) return genFromRow(a.data);
    const b = await this.db.from("generations").update({ status: "processing", updated_at: nowIso }).eq("id", id).eq("status", "processing").lt("updated_at", staleBefore).select("*").maybeSingle();
    if (b.error) throw new Error(b.error.message);
    return b.data ? genFromRow(b.data) : null;
  }
  async listGenerations(sessionId: string) {
    const { data, error } = await this.db.from("generations").select("*").eq("session_id", sessionId).order("created_at");
    if (error) throw new Error(error.message);
    return (data ?? []).map(genFromRow);
  }
  async createShare(s: Omit<Share, "createdAt">) {
    const res = await this.db
      .from("shares")
      .insert({
        id: s.id,
        session_id: s.sessionId,
        face_generation_id: s.faceGenerationId,
        photo_generation_id: s.photoGenerationId,
        after_path: s.afterPath,
        variant_paths: s.variantPaths,
        variant_labels: s.variantLabels,
        chosen_index: s.chosenIndex,
        photo_paths: s.photoPaths,
        og_path: s.ogPath,
        story_paths: s.storyPaths,
        caption: s.caption,
        expires_at: s.expiresAt,
      })
      .select("*")
      .single();
    return shareFromRow(must(res, "createShare"));
  }
  async getShare(id: string) {
    const { data, error } = await this.db.from("shares").select("*").eq("id", id).maybeSingle();
    if (error) throw new Error(error.message);
    return data ? shareFromRow(data) : null;
  }
  async listShares(sessionId: string) {
    const { data, error } = await this.db.from("shares").select("*").eq("session_id", sessionId);
    if (error) throw new Error(error.message);
    return (data ?? []).map(shareFromRow);
  }
  async castVote(shareId: string, voterKey: string, choice: string) {
    const { error } = await this.db.from("votes").upsert({ share_id: shareId, voter_key: voterKey, choice }, { onConflict: "share_id,voter_key" });
    if (error) throw new Error(error.message);
  }
  async getVote(shareId: string, voterKey: string) {
    const { data, error } = await this.db.from("votes").select("choice").eq("share_id", shareId).eq("voter_key", voterKey).maybeSingle();
    if (error) throw new Error(error.message);
    return (data?.choice as string) ?? null;
  }
  async getVoteTally(shareId: string): Promise<VoteTally> {
    const { data, error } = await this.db.from("votes").select("choice").eq("share_id", shareId);
    if (error) throw new Error(error.message);
    const tally: VoteTally = {};
    for (const r of data ?? []) tally[r.choice as string] = (tally[r.choice as string] ?? 0) + 1;
    return tally;
  }
  async logEvent(e: Omit<EventRow, "createdAt">) {
    const { error } = await this.db.from("events").insert({ session_id: e.sessionId, name: e.name, props: e.props });
    if (error) console.error("logEvent", error.message);
  }
  async addToWaitlist(email: string, sessionId: string | null) {
    const { error } = await this.db.from("waitlist").upsert({ email, session_id: sessionId }, { onConflict: "email", ignoreDuplicates: true });
    if (error) throw new Error(error.message);
  }
  async deleteSessionData(sessionId: string): Promise<CleanupReport> {
    const [uploads, gens, shares] = await Promise.all([
      this.listUploads(sessionId),
      this.listGenerations(sessionId),
      this.listShares(sessionId),
    ]);
    const report = await this.purge(uploads, gens, shares);
    const { error } = await this.db
      .from("sessions")
      .update({ current_upload_id: null, current_face_generation_id: null, current_photo_generation_id: null })
      .eq("id", sessionId);
    if (error) throw new Error(`deleteSessionData: ${error.message}`);
    return report;
  }
  async cleanupExpired(now: Date): Promise<CleanupReport> {
    const iso = now.toISOString();
    const [u, g, s] = await Promise.all([
      this.db.from("uploads").select("*").lte("expires_at", iso).limit(500),
      this.db.from("generations").select("*").lte("expires_at", iso).limit(500),
      this.db.from("shares").select("*").lte("expires_at", iso).limit(500),
    ]);
    if (u.error) throw new Error(u.error.message);
    if (g.error) throw new Error(g.error.message);
    if (s.error) throw new Error(s.error.message);
    const report = await this.purge((u.data ?? []).map(uploadFromRow), (g.data ?? []).map(genFromRow), (s.data ?? []).map(shareFromRow));
    // 만료된 항목을 가리키는 세션 포인터를 정리한다.
    const upIds = (u.data ?? []).map((r) => r.id as string);
    const genIds = (g.data ?? []).map((r) => r.id as string);
    const unlink = async (col: string, ids: string[]) => {
      if (!ids.length) return;
      const { error } = await this.db.from("sessions").update({ [col]: null }).in(col, ids);
      if (error) throw new Error(`cleanupExpired ${col}: ${error.message}`);
    };
    await unlink("current_upload_id", upIds);
    await unlink("current_face_generation_id", genIds);
    await unlink("current_photo_generation_id", genIds);
    return report;
  }
  private async purge(uploads: Upload[], gens: Generation[], shares: Share[]): Promise<CleanupReport> {
    const priv = [...uploads.map((x) => x.path), ...shares.flatMap((x) => x.storyPaths), ...gens.flatMap(privateGenerationPaths)];
    const pub = [...gens.flatMap((x) => x.outputPaths), ...shares.map((x) => x.ogPath)];
    await this.deleteBlobs("private", priv);
    await this.deleteBlobs("public", pub);
    const del = async (table: string, ids: string[]) => {
      if (!ids.length) return;
      const { error } = await this.db.from(table).delete().in("id", ids);
      if (error) throw new Error(`purge ${table}: ${error.message}`);
    };
    await del("shares", shares.map((x) => x.id));
    await del("generations", gens.map((x) => x.id));
    await del("uploads", uploads.map((x) => x.id));
    return { uploads: uploads.length, generations: gens.length, shares: shares.length, blobs: priv.length + pub.length };
  }
  async putBlob(bucket: Bucket, path: string, data: Buffer, contentType: string) {
    const { error } = await this.db.storage.from(bucket).upload(path, data, { contentType, upsert: true });
    if (error) throw new Error(`putBlob: ${error.message}`);
  }
  async getBlob(bucket: Bucket, path: string) {
    const { data, error } = await this.db.storage.from(bucket).download(path);
    if (error || !data) return null;
    return Buffer.from(await data.arrayBuffer());
  }
  async deleteBlobs(bucket: Bucket, paths: string[]) {
    if (!paths.length) return;
    // 한 번에 너무 많이 보내지 않도록 100개씩 끊는다.
    for (let i = 0; i < paths.length; i += 100) {
      const { error } = await this.db.storage.from(bucket).remove(paths.slice(i, i + 100));
      if (error) throw new Error(`deleteBlobs: ${error.message}`);
    }
  }
  async signedUrl(bucket: Bucket, path: string, expiresSeconds: number) {
    const { data, error } = await this.db.storage.from(bucket).createSignedUrl(path, expiresSeconds);
    if (error || !data) throw new Error(`signedUrl: ${error?.message}`);
    return data.signedUrl;
  }
  publicUrl(path: string) {
    return this.db.storage.from("public").getPublicUrl(path).data.publicUrl;
  }
}

