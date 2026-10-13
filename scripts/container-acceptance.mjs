import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { randomUUID, randomBytes } from "node:crypto";
import { execFileSync } from "node:child_process";
const origin = "https://localhost:8443",
  credentials = JSON.parse(readFileSync(".local/browser.json", "utf8"));
let cookie = "";
async function req(path, method = "GET", body) {
  const r = await fetch(origin + path, {
    redirect: "manual",
    method,
    headers: {
      cookie,
      ...(body ? { origin, "content-type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: r.status, headers: r.headers, data: await r.text() };
}
let r = await req("/health");
assert.equal(r.status, 200);
assert.deepEqual(JSON.parse(r.data), { status: "ok" });
r = await req("/api/admin/login", "POST", credentials);
assert.equal(r.status, 200, r.data);
assert.match(r.headers.get("set-cookie"), /Secure/);
assert.match(r.headers.get("set-cookie"), /HttpOnly/);
cookie = r.headers.get("set-cookie").split(";")[0];
r = await req("/api/admin/garments", "POST", {
  name: "容器TLS验收服装",
  item_code: randomUUID(),
  status: "PUBLISHED",
});
assert.equal(r.status, 201, r.data);
const g = JSON.parse(r.data);
r = await req("/api/admin/tags", "POST", {
  uid: randomBytes(7).toString("hex"),
  garmentId: g.id,
  notes: "模拟容器验收",
});
assert.equal(r.status, 201, r.data);
const t = JSON.parse(r.data);
r = await req("/t/" + t.entry_code);
assert.equal(r.status, 302);
assert.equal(r.headers.get("location"), "/g/" + g.id);
assert.equal(r.headers.get("cache-control"), "no-store");
r = await req("/g/" + g.id);
assert.equal(r.status, 200);
assert.ok(r.data.includes(g.name));
assert.ok(!r.data.includes(t.uid));
assert.ok(!r.data.includes(t.entry_code));
assert.equal(r.headers.get("cache-control"), "no-store");
execFileSync(
  "docker",
  [
    "compose",
    "-f",
    "compose.yaml",
    "-f",
    ".local/compose.acceptance.yaml",
    "restart",
    "app",
  ],
  { stdio: "pipe" },
);
let healthy = false;
for (let i = 0; i < 30; i++) {
  try {
    if ((await req("/health")).status === 200) {
      healthy = true;
      break;
    }
  } catch {}
  await new Promise((r) => setTimeout(r, 500));
}
assert.ok(healthy);
assert.equal((await req("/api/admin/garments/" + g.id)).status, 200);
assert.equal(
  (await req("/t/" + t.entry_code)).headers.get("location"),
  "/g/" + g.id,
);
const inspect = JSON.parse(
  execFileSync("docker", ["inspect", "bumbum-app-1"], { encoding: "utf8" }),
)[0];
assert.equal(inspect.Config.User, "node");
assert.deepEqual(inspect.HostConfig.PortBindings, {});
assert.equal(inspect.HostConfig.ReadonlyRootfs, true);
const env = inspect.Config.Env.find((x) => x.startsWith("DATABASE_URL="));
assert.ok(env.includes("bumbum_app:"));
assert.ok(!inspect.Config.Env.some((x) => x.includes("bumbum_migrate")));
const files = execFileSync(
  "docker",
  [
    "run",
    "--rm",
    "--entrypoint",
    "sh",
    "bumbum:1.0.0",
    "-c",
    "test ! -e /app/.env && test ! -e /app/.env.migrate && test ! -d /app/.local && test ! -d /app/secrets && test ! -d /app/tests && echo clean",
  ],
  { encoding: "utf8" },
);
assert.match(files, /clean/);
console.log(
  "PASS: TLS HTTPS proxy, Secure cookie, login/create/tag/302/privacy, container restart/persistence, non-root/read-only/no published 3000, app-only credentials, no secret files in image",
);
