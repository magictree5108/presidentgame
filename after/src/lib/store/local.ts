import { promises as fs } from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { appUrl } from "@/lib/brand";
import type { CreditKind } from "@/lib/config";
import { privateGenerationPaths } from "./paths";
import type { Bucket, CleanupReport, EventRow, Generation, RateLimitResult, Session, Share, Store, Upload, VoteTally } from "./types";

/**
 * 파일 기반 로컬 저장소. Supabase 키 없이 개발할 때만 쓴다 (STORE_DRIVER=local).
 * 데이터는 프로젝트 루트의 .local-data/ 아래에 저장된다. 프로덕션에서는 절대 쓰지 말 것.
 */

type Db = {
  sessions: Record<string, Session>;
  uploads: Record<string, Upload>;
  generations: Record<string, Generation>;
  shares: Record<string, Share>;
  waitlist: Array<{ email: string; sessionId: string | null; createdAt: string }>;
  rateLimits: Record<string, { windowStart: number; count: number }>;
  votes?: Record<string, Record<string, string>>; // shareId → voterKey → choice
  events?: EventRow[];
};

const ROOT = path.join(process.cwd(), ".local-data");
const DB_FILE = path.join(ROOT, "db.json");
const BLOB_ROOT = path.join(ROOT, "blobs");
const SIGN_SECRET = process.env.LOCAL_SIGN_SECRET || "local-dev-secret";

// 전역 캐시: Next dev 의 HMR 로 모듈이 다시 로드돼도 상태를 잃지 않게 globalThis 에 둔다.
const g = globalThis as unknown as { __afterLocalDb?: Db; __afterLocalLock?: Promise<void> };

async function load(): Promise<Db> {
  if (g.__afterLocalDb) return g.__afterLocalDb;
  try {
    const raw = await fs.readFile(DB_FILE, "utf8");
    g.__afterLocalDb = JSON.parse(raw) as Db;
  } catch {
    g.__afterLocalDb = { sessions: {}, uploads: {}, generations: {}, shares: {}, waitlist: [], rateLimits: {} };
  }
  return g.__afterLocalDb!;
}

async function save(db: Db) {
  await fs.mkdir(ROOT, { recursive: true });
  await fs.writeFile(DB_FILE, JSON.stringify(db, null, 2));
}

/** 아주 단순한 직렬화 락. 동시 요청이 db.json 을 겹쳐 쓰지 않게 한다. */
async function withLock<T>(fn: (db: Db) => Promise<T>): Promise<T> {
  const prev = g.__afterLocalLock ?? Promise.resolve();
  let release!: () => void;
  g.__afterLocalLock = new Promise<void>((r) => (release = r));
  try {
    await prev;
    const db = await load();
    const out = await fn(db);
    await save(db);
    return out;
  } finally {
    release();
  }
}

const now = () => new Date().toISOString();
const uuid = () => crypto.randomUUID();

function sign(bucket: string, p: string, exp: number) {
  return crypto.createHmac("sha256", SIGN_SECRET).update(`${bucket}:${p}:${exp}`).digest("hex").slice(0, 32);
}

export function verifyLocalSignature(bucket: string, p: string, exp: number, sig: string) {
  if (Date.now() / 1000 > exp) return false;
  const expected = sign(bucket, p, exp);
  return expected.length === sig.length && crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(sig));
}

function blobPath(bucket: Bucket, p: string) {
  const full = path.join(BLOB_ROOT, bucket, p);
  if (!full.startsWith(path.join(BLOB_ROOT, bucket))) throw new Error("invalid blob path");
  return full;
}

export class LocalStore implements Store {
  async getSession(id: string) {
    const db = await load();
    return db.sessions[id] ?? null;
  }
  async createSession(id: string, init: { ageConfirmedAt: string; consentAt: string; faceCredits: number; photoCredits: number }) {
    return withLock(async (db) => {
      const s: Session = {
        id,
        createdAt: now(),
        ageConfirmedAt: init.ageConfirmedAt,
        consentAt: init.consentAt,
        faceCredits: init.faceCredits,
        photoCredits: init.photoCredits,
        currentUploadId: null,
        currentFaceGenerationId: null,
        currentPhotoGenerationId: null,
        selection: null,
      };
      db.sessions[id] = s;
      return s;
    });
  }
  async updateSession(id: string, patch: Partial<Session>) {
    return withLock(async (db) => {
      const s = db.sessions[id];
      if (!s) throw new Error("session not found");
      Object.assign(s, patch);
      return s;
    });
  }
  async consumeCredits(sessionId: string, kind: CreditKind, amount: number) {
    return withLock(async (db) => {
      const s = db.sessions[sessionId];
      if (!s) return false;
      const key = kind === "face" ? "faceCredits" : "photoCredits";
      if (s[key] < amount) return false;
      s[key] -= amount;
      return true;
    });
  }
  async refundCredits(sessionId: string, kind: CreditKind, amount: number) {
    await withLock(async (db) => {
      const s = db.sessions[sessionId];
      if (!s) return;
      const key = kind === "face" ? "faceCredits" : "photoCredits";
      s[key] += amount;
    });
  }
  async checkRateLimit(sessionId: string, key: string, limit: number, windowSeconds: number): Promise<RateLimitResult> {
    return withLock(async (db) => {
      const k = `${sessionId}:${key}`;
      const t = Date.now();
      const cur = db.rateLimits[k];
      if (!cur || t - cur.windowStart > windowSeconds * 1000) {
        db.rateLimits[k] = { windowStart: t, count: 1 };
        return { allowed: true, retryAfterSeconds: 0 };
      }
      if (cur.count >= limit) {
        return { allowed: false, retryAfterSeconds: Math.ceil((cur.windowStart + windowSeconds * 1000 - t) / 1000) };
      }
      cur.count += 1;
      return { allowed: true, retryAfterSeconds: 0 };
    });
  }
  async createUpload(u: Omit<Upload, "id" | "createdAt">) {
    return withLock(async (db) => {
      const up: Upload = { ...u, id: uuid(), createdAt: now() };
      db.uploads[up.id] = up;
      return up;
    });
  }
  async getUpload(id: string) {
    return (await load()).uploads[id] ?? null;
  }
  async listUploads(sessionId: string) {
    return Object.values((await load()).uploads).filter((u) => u.sessionId === sessionId);
  }
  async deleteUploads(ids: string[]) {
    await withLock(async (db) => {
      for (const id of ids) delete db.uploads[id];
    });
  }
  async createGeneration(gen: Omit<Generation, "id" | "createdAt" | "updatedAt">) {
    return withLock(async (db) => {
      const g2: Generation = { ...gen, id: uuid(), createdAt: now(), updatedAt: now() };
      db.generations[g2.id] = g2;
      return g2;
    });
  }
  async getGeneration(id: string) {
    return (await load()).generations[id] ?? null;
  }
  async updateGeneration(id: string, patch: Partial<Generation>) {
    return withLock(async (db) => {
      const g2 = db.generations[id];
      if (!g2) throw new Error("generation not found");
      Object.assign(g2, patch, { updatedAt: now() });
      return g2;
    });
  }
  async claimGeneration(id: string, staleBefore: string) {
    return withLock(async (db) => {
      const g2 = db.generations[id];
      if (!g2) return null;
      const claimable = g2.status === "queued" || g2.status === "running" || (g2.status === "processing" && g2.updatedAt < staleBefore);
      if (!claimable) return null;
      Object.assign(g2, { status: "processing", updatedAt: now() });
      return g2;
    });
  }
  async listGenerations(sessionId: string) {
    return Object.values((await load()).generations).filter((x) => x.sessionId === sessionId);
  }
  async createShare(s: Omit<Share, "createdAt">) {
    return withLock(async (db) => {
      const sh: Share = { ...s, createdAt: now() };
      db.shares[sh.id] = sh;
      return sh;
    });
  }
  async getShare(id: string) {
    return (await load()).shares[id] ?? null;
  }
  async listShares(sessionId: string) {
    return Object.values((await load()).shares).filter((x) => x.sessionId === sessionId);
  }
  async castVote(shareId: string, voterKey: string, choice: string) {
    await withLock(async (db) => {
      db.votes ??= {};
      db.votes[shareId] ??= {};
      db.votes[shareId][voterKey] = choice;
    });
  }
  async getVote(shareId: string, voterKey: string) {
    return (await load()).votes?.[shareId]?.[voterKey] ?? null;
  }
  async getVoteTally(shareId: string): Promise<VoteTally> {
    const v = (await load()).votes?.[shareId] ?? {};
    const tally: VoteTally = {};
    for (const c of Object.values(v)) tally[c] = (tally[c] ?? 0) + 1;
    return tally;
  }
  async logEvent(e: Omit<EventRow, "createdAt">) {
    await withLock(async (db) => {
      db.events ??= [];
      db.events.push({ ...e, createdAt: now() });
      if (db.events.length > 5000) db.events.splice(0, db.events.length - 5000);
    });
  }
  async addToWaitlist(email: string, sessionId: string | null) {
    await withLock(async (db) => {
      if (!db.waitlist.some((w) => w.email === email)) db.waitlist.push({ email, sessionId, createdAt: now() });
    });
  }
  async deleteSessionData(sessionId: string): Promise<CleanupReport> {
    const uploads = await this.listUploads(sessionId);
    const gens = await this.listGenerations(sessionId);
    const shares = await this.listShares(sessionId);
    return this.purge(uploads, gens, shares, true);
  }
  async cleanupExpired(at: Date): Promise<CleanupReport> {
    const db = await load();
    const t = at.getTime();
    const exp = (x: { expiresAt: string }) => new Date(x.expiresAt).getTime() <= t;
    return this.purge(
      Object.values(db.uploads).filter(exp),
      Object.values(db.generations).filter(exp),
      Object.values(db.shares).filter(exp),
      false,
    );
  }
  private async purge(uploads: Upload[], gens: Generation[], shares: Share[], resetSession: boolean): Promise<CleanupReport> {
    let blobs = 0;
    const priv = [...uploads.map((u) => u.path), ...shares.flatMap((s) => s.storyPaths), ...gens.flatMap(privateGenerationPaths)];
    const pub = [...gens.flatMap((g) => g.outputPaths), ...shares.map((s) => s.ogPath)];
    await this.deleteBlobs("private", priv);
    await this.deleteBlobs("public", pub);
    blobs = priv.length + pub.length;
    await withLock(async (db) => {
      for (const u of uploads) delete db.uploads[u.id];
      for (const g2 of gens) delete db.generations[g2.id];
      for (const s of shares) {
        delete db.shares[s.id];
        if (db.votes) delete db.votes[s.id];
      }
      if (resetSession) {
        for (const s of Object.values(db.sessions)) {
          if (uploads.some((u) => u.sessionId === s.id) || gens.some((g2) => g2.sessionId === s.id)) {
            s.currentUploadId = null;
            s.currentFaceGenerationId = null;
            s.currentPhotoGenerationId = null;
          }
        }
      } else {
        // 만료로 지워진 항목을 가리키는 세션 포인터 정리
        for (const s of Object.values(db.sessions)) {
          if (s.currentUploadId && !db.uploads[s.currentUploadId]) s.currentUploadId = null;
          if (s.currentFaceGenerationId && !db.generations[s.currentFaceGenerationId]) s.currentFaceGenerationId = null;
          if (s.currentPhotoGenerationId && !db.generations[s.currentPhotoGenerationId]) s.currentPhotoGenerationId = null;
        }
      }
    });
    return { uploads: uploads.length, generations: gens.length, shares: shares.length, blobs };
  }
  async putBlob(bucket: Bucket, p: string, data: Buffer) {
    const full = blobPath(bucket, p);
    await fs.mkdir(path.dirname(full), { recursive: true });
    await fs.writeFile(full, data);
  }
  async getBlob(bucket: Bucket, p: string) {
    try {
      return await fs.readFile(blobPath(bucket, p));
    } catch {
      return null;
    }
  }
  async deleteBlobs(bucket: Bucket, paths: string[]) {
    await Promise.all(paths.map((p) => fs.rm(blobPath(bucket, p), { force: true })));
  }
  async signedUrl(bucket: Bucket, p: string, expiresSeconds: number) {
    const exp = Math.floor(Date.now() / 1000) + expiresSeconds;
    const sig = sign(bucket, p, exp);
    return `${appUrl()}/api/blob/${bucket}/${p}?exp=${exp}&sig=${sig}`;
  }
  publicUrl(p: string) {
    return `${appUrl()}/api/blob/public/${p}`;
  }
}
