import assert from "node:assert/strict";
import { db, poolFor } from "./dist/db.js";
const [ssl] = await db.query("SHOW SESSION STATUS LIKE 'Ssl_cipher'");
assert.ok(ssl[0].Value);
await db.end();
const bad = new URL(process.env.DATABASE_URL);
bad.hostname = "wrong-mysql";
const mismatch = poolFor(bad.toString());
await assert.rejects(
  () => mismatch.query("SELECT 1"),
  (e) => e.code === "HANDSHAKE_SSL_ERROR" && e.message.includes("altnames"),
);
await mismatch.end();
process.env.DB_CA_FILE = "/run/wrong-ca.pem";
const wrongCA = poolFor(process.env.DATABASE_URL);
await assert.rejects(() => wrongCA.query("SELECT 1"));
await wrongCA.end();
process.env.DB_TLS = "false";
assert.throws(() => poolFor(process.env.DATABASE_URL), /Production requires/);
console.log(
  "PASS: encrypted MySQL with CA/identity verification, wrong hostname/CA rejected, plaintext prohibited in production",
);
