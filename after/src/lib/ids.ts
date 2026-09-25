import crypto from "node:crypto";
/** 공유 링크용 짧은 ID (8자, URL-safe). */
export function newShareId() {
  return crypto.randomBytes(6).toString("base64url");
}
