import {
  randomBytes,
  scryptSync,
  timingSafeEqual,
  createHmac,
} from "node:crypto";
export function hashPassword(p: string) {
  const salt = randomBytes(16).toString("hex");
  return `scrypt$${salt}$${scryptSync(p, salt, 64).toString("hex")}`;
}
export function verifyPassword(p: string, h: string) {
  const [, salt, key] = h.split("$");
  if (!salt || !key) return false;
  const k = Buffer.from(key, "hex");
  const actual = scryptSync(p, salt, 64);
  return k.length === actual.length && timingSafeEqual(k, actual);
}
export function tokenHash(t: string) {
  return createHmac("sha256", process.env.SESSION_SECRET!)
    .update(t)
    .digest("hex");
}
