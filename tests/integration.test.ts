import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { randomUUID, randomBytes, createHash } from "node:crypto";
import { writeFileSync } from "node:fs";
import { spawnSync, execFileSync } from "node:child_process";
import { once } from "node:events";
import { app } from "../src/app.js";
import { db, poolFor, rows } from "../src/db.js";
import { hashPassword } from "../src/security.js";
if (
  process.env.NODE_ENV === "production" ||
  !process.env.DATABASE_URL?.endsWith("/bumbum_test")
)
  throw Error("Tests require isolated bumbum_test database");
const migration = poolFor(process.env.TEST_MIGRATION_URL!);
const adminName = "test-" + randomUUID(),
  password = randomBytes(16).toString("hex");
let server: any,
  origin: string,
  cookie = "",
  A: any,
  B: any,
  TA: any,
  TB: any;
async function request(
  path: string,
  method = "GET",
  body?: any,
  options: any = {},
) {
  const r = await fetch(origin + path, {
    method,
    redirect: "manual",
    headers: {
      ...(options.anonymous ? {} : { cookie }),
      ...(body
        ? {
            "content-type": "application/json",
            origin: options.origin || "http://localhost:3000",
          }
        : {}),
      ...options.headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  let data: any;
  try {
    data = JSON.parse(text);
  } catch {}
  return { status: r.status, headers: r.headers, text, data };
}
const api = (p: string, m = "GET", b?: any, o?: any) =>
  request("/api/admin" + p, m, b, o);
const check = (r: any, status = 200) => {
  assert.equal(r.status, status, r.text);
  return r.data;
};
function rootSQL(sql: string) {
  const p = spawnSync(
    "docker",
    [
      "compose",
      "-f",
      "compose.local.yaml",
      "exec",
      "-T",
      "mysql",
      "sh",
      "-c",
      'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot',
    ],
    { input: sql, encoding: "utf8" },
  );
  assert.equal(p.status, 0, p.stderr);
}
before(async () => {
  await migration.execute(
    "INSERT INTO admins(id,username,password_hash) VALUES (?,?,?)",
    [randomUUID(), adminName, hashPassword(password)],
  );
  server = app.listen(0, "127.0.0.1");
  await once(server, "listening");
  origin = `http://127.0.0.1:${server.address().port}`;
});
after(async () => {
  await new Promise<void>((r) => server.close(() => r()));
  await db.end();
  await migration.end();
});
test("01 authentication, strict origin, cookie flags and request errors", async () => {
  check(await api("/garments", "GET", undefined, { anonymous: true }), 401);
  assert.equal(
    (
      await request("/admin/garments", "GET", undefined, { anonymous: true })
    ).headers.get("location"),
    "/admin/login",
  );
  check(
    await api(
      "/login",
      "POST",
      { username: adminName, password },
      { origin: "https://evil.example" },
    ),
    403,
  );
  const r = await api("/login", "POST", { username: adminName, password });
  check(r);
  const set = r.headers.get("set-cookie")!;
  assert.match(set, /HttpOnly/i);
  assert.match(set, /SameSite=Strict/i);
  cookie = set.split(";")[0];
  check(await api("/me"));
  check(
    await api(
      "/garments",
      "POST",
      { name: "X", item_code: "X" },
      { origin: "https://evil.example" },
    ),
    403,
  );
});
test("02 create A/B, normalized unique UID and correct 302/no-store mapping", async () => {
  const suffix = randomUUID().slice(0, 8);
  A = check(
    await api("/garments", "POST", {
      name: "黑色外套",
      item_code: "item-a-" + suffix,
      status: "PUBLISHED",
      description: "<script>alert(1)</script>",
      image_url: "https://images.invalid/missing.png",
    }),
    201,
  );
  B = check(
    await api("/garments", "POST", {
      name: "白色衬衫",
      item_code: "ITEM-B-" + suffix,
      status: "PUBLISHED",
    }),
    201,
  );
  TA = check(
    await api("/tags", "POST", {
      uid: randomBytes(7).toString("hex").match(/../g)!.join(":"),
      notes: "模拟标签 A",
      garmentId: A.id,
    }),
    201,
  );
  TB = check(
    await api("/tags", "POST", {
      uid: randomBytes(7).toString("hex"),
      notes: "模拟标签 B",
      garmentId: B.id,
    }),
    201,
  );
  assert.match(TA.uid, /^[0-9A-F]{14}$/);
  assert.notEqual(TA.entry_code, TB.entry_code);
  for (const [t, g] of [
    [TA, A],
    [TB, B],
  ]) {
    const r = await request("/t/" + t.entry_code);
    assert.equal(r.status, 302);
    assert.equal(r.headers.get("location"), "/g/" + g.id);
    assert.equal(r.headers.get("cache-control"), "no-store");
  }
  check(await api("/tags", "POST", { uid: TA.uid }), 409);
  check(await api("/tags", "POST", { uid: "xyz" }), 400);
});
test("03 fields validation, XSS escaping, pagination and forbidden owner update", async () => {
  check(
    await api("/garments", "POST", {
      name: "x".repeat(101),
      item_code: "too-long",
    }),
    400,
  );
  check(await api("/garments", "PATCH", { version: 1 }), 404);
  check(
    await api("/garments/" + A.id, "PATCH", {
      version: A.version,
      owner_phone: "13800000001",
    }),
    400,
  );
  check(
    await api("/garments/" + A.id, "PATCH", {
      version: A.version,
      image_url: "javascript:alert(1)",
    }),
    400,
  );
  check(
    await api("/garments/" + A.id + "/owner", "PATCH", {
      version: A.version,
      phone: "123",
      reason: "测试",
    }),
    400,
  );
  check(await api("/garments?page=0"), 400);
  check(await api("/garments?pageSize=101"), 400);
  const r = await request("/g/" + A.id);
  assert.match(r.text, /&lt;script&gt;/);
  assert.doesNotMatch(r.text, /<script>alert/);
  assert.equal(r.headers.get("cache-control"), "no-store");
});
test("04 owner changes atomic auditing, no-op and public whitelist/privacy", async () => {
  for (const phone of ["13800000001", "13900000002"])
    A = check(
      await api("/garments/" + A.id + "/owner", "PATCH", {
        phone,
        reason: "虚拟测试号码",
        version: A.version,
      }),
    );
  const logs = check(
    await api(`/audit-logs?entityType=garment&entityId=${A.id}`),
  );
  assert.equal(
    logs.items.filter((x: any) => x.action === "OWNER_CHANGE").length,
    2,
  );
  assert.doesNotMatch(JSON.stringify(logs), /13900000002/);
  const full = check(
    await api(
      "/audit-logs/" +
        logs.items.find((x: any) => x.action === "OWNER_CHANGE").id,
    ),
  );
  assert.match(JSON.stringify(full), /13900000002|13800000001/);
  const unchanged = check(
    await api("/garments/" + A.id + "/owner", "PATCH", {
      phone: A.owner_phone,
      reason: "无变化",
      version: A.version,
    }),
  );
  assert.equal(unchanged.version, A.version);
  for (const path of ["/g/" + A.id, "/api/public/garments/" + A.id]) {
    const r = await request(path);
    check(r);
    assert.equal(r.headers.get("cache-control"), "no-store");
    for (const value of [
      A.owner_phone,
      TA.uid,
      TA.entry_code,
      "owner_phone",
      "admin_id",
      "password_hash",
    ])
      assert.ok(!r.text.includes(value), value);
  }
  const list = check(await api("/garments?q=" + A.item_code));
  assert.equal(list.items[0].owner_phone, "139****0002");
});
test("05 immediate updated content and optimistic concurrency", async () => {
  const old = A.version;
  A = check(
    await api("/garments/" + A.id, "PATCH", {
      name: "更新后的黑色外套",
      version: old,
    }),
  );
  check(
    await api("/garments/" + A.id, "PATCH", { name: "过期修改", version: old }),
    409,
  );
  assert.match((await request("/g/" + A.id)).text, /更新后的黑色外套/);
});
test("06 conflict and rebind keeps original garment ownership", async () => {
  check(
    await api("/tags/" + TA.id + "/binding", "PUT", {
      garmentId: B.id,
      reason: "冲突测试",
      version: TA.version,
    }),
    409,
  );
  assert.equal(check(await api("/tags/" + TA.id)).garment_id, A.id);
  TB = check(
    await api("/tags/" + TB.id + "/binding", "PUT", {
      garmentId: null,
      reason: "释放 B",
      version: TB.version,
    }),
  );
  TA = check(
    await api("/tags/" + TA.id + "/binding", "PUT", {
      garmentId: B.id,
      reason: "改绑 B",
      version: TA.version,
    }),
  );
  assert.equal(
    (await request("/t/" + TA.entry_code)).headers.get("location"),
    "/g/" + B.id,
  );
  assert.equal(
    check(await api("/garments/" + A.id)).owner_phone,
    A.owner_phone,
  );
  assert.equal(check(await api("/garments/" + B.id)).owner_phone, null);
});
test("07 disabled/unbound/unknown/draft/archived readable states", async () => {
  TA = check(
    await api("/tags/" + TA.id, "PATCH", {
      enabled: false,
      version: TA.version,
    }),
  );
  const disabled = await request("/t/" + TA.entry_code);
  check(disabled, 410);
  assert.match(disabled.text, /已停用/);
  assert.equal(disabled.headers.get("cache-control"), "no-store");
  TA = check(
    await api("/tags/" + TA.id, "PATCH", {
      enabled: true,
      version: TA.version,
    }),
  );
  check(await request("/t/" + TA.entry_code), 302);
  for (const status of ["DRAFT", "ARCHIVED"]) {
    B = check(
      await api("/garments/" + B.id, "PATCH", { status, version: B.version }),
    );
    check(await request("/t/" + TA.entry_code), 404);
    check(await request("/g/" + B.id), 404);
    check(await request("/api/public/garments/" + B.id), 404);
  }
  B = check(
    await api("/garments/" + B.id, "PATCH", {
      status: "PUBLISHED",
      version: B.version,
    }),
  );
  const unbound = await request("/t/" + TB.entry_code);
  check(unbound, 409);
  assert.match(unbound.text, /尚未关联/);
  check(await request("/t/" + randomBytes(16).toString("hex")), 404);
  check(await request("/t/bad"), 404);
  check(await request("/g/" + randomUUID()), 404);
});
test("08 two concurrent tags compete for one garment without overwrite", async () => {
  const C = check(
    await api("/garments", "POST", {
      name: "并发测试",
      item_code: randomUUID(),
    }),
    201,
  );
  const t1 = check(
      await api("/tags", "POST", { uid: randomBytes(7).toString("hex") }),
      201,
    ),
    t2 = check(
      await api("/tags", "POST", { uid: randomBytes(7).toString("hex") }),
      201,
    );
  const rs = await Promise.all(
    [t1, t2].map((t) =>
      api(`/tags/${t.id}/binding`, "PUT", {
        garmentId: C.id,
        reason: "并发",
        version: t.version,
      }),
    ),
  );
  assert.deepEqual(rs.map((r) => r.status).sort(), [200, 409]);
  assert.equal(
    (await rows("SELECT * FROM tags WHERE garment_id=?", [C.id])).length,
    1,
  );
  const current = check(await api("/tags/" + t1.id));
  const rs2 = await Promise.all(
    [true, false].map((enabled) =>
      api("/tags/" + t1.id, "PATCH", { enabled, version: current.version }),
    ),
  );
  assert.deepEqual(rs2.map((r) => r.status).sort(), [200, 409]);
});
test("09 audit insert failure rolls back owner and binding transactions", async () => {
  const before = check(await api("/garments/" + A.id)),
    tag = check(await api("/tags/" + TA.id));
  const [{ n: count }] = await rows(
    "SELECT COUNT(*) n FROM audit_logs WHERE entity_id=?",
    [A.id],
  );
  rootSQL("REVOKE INSERT ON bumbum_test.audit_logs FROM 'bumbum_app'@'%';");
  try {
    check(
      await api("/garments/" + A.id + "/owner", "PATCH", {
        phone: "13700000003",
        reason: "回滚测试",
        version: before.version,
      }),
      500,
    );
    check(
      await api("/tags/" + TA.id + "/binding", "PUT", {
        garmentId: null,
        reason: "回滚测试",
        version: tag.version,
      }),
      500,
    );
  } finally {
    rootSQL("GRANT INSERT ON bumbum_test.audit_logs TO 'bumbum_app'@'%';");
  }
  const after = check(await api("/garments/" + A.id));
  assert.equal(after.owner_phone, before.owner_phone);
  assert.equal(after.version, before.version);
  assert.equal(check(await api("/tags/" + TA.id)).garment_id, tag.garment_id);
  assert.equal(
    (
      await rows("SELECT COUNT(*) n FROM audit_logs WHERE entity_id=?", [A.id])
    )[0].n,
    count,
  );
  await assert.rejects(() => db.execute("DELETE FROM audit_logs"));
  await assert.rejects(() => db.execute("CREATE TABLE forbidden(id INT)"));
});
test("10 clear owner and manual verification immutable UID", async () => {
  A = check(
    await api("/garments/" + A.id + "/owner", "PATCH", {
      phone: null,
      reason: "清空登记",
      version: A.version,
    }),
  );
  assert.equal(
    check(await request("/api/public/garments/" + A.id)).ownerRegistered,
    false,
  );
  check(
    await api("/tags/" + TA.id, "PATCH", {
      uid: "00112233445566",
      version: TA.version,
    }),
    400,
  );
  TA = check(
    await api("/tags/" + TA.id + "/write-verification", "POST", {
      version: TA.version,
    }),
  );
  assert.ok(TA.write_verified_at);
  check(
    await api("/tags/" + TA.id + "/write-verification", "POST", {
      version: TA.version - 1,
    }),
    409,
  );
});
test("11 every administrative resource protected without session", async () => {
  const paths = [
    ["GET", "/me"],
    ["GET", "/garments"],
    ["POST", "/garments"],
    ["GET", "/garments/" + A.id],
    ["PATCH", "/garments/" + A.id],
    ["PATCH", "/garments/" + A.id + "/owner"],
    ["GET", "/tags"],
    ["POST", "/tags"],
    ["GET", "/tags/" + TA.id],
    ["PATCH", "/tags/" + TA.id],
    ["PUT", "/tags/" + TA.id + "/binding"],
    ["POST", "/tags/" + TA.id + "/write-verification"],
    ["GET", "/audit-logs"],
    ["GET", "/audit-logs/" + randomUUID()],
    ["POST", "/logout"],
  ];
  for (const [method, path] of paths)
    check(
      await api(path, method, method === "GET" ? undefined : {}, {
        anonymous: true,
      }),
      401,
    );
});
test("12 login rate limit survives new session and wrong username/password unify", async () => {
  const username = "missing-" + randomUUID();
  for (let i = 0; i < 5; i++) {
    const r = await api("/login", "POST", { username, password: "wrong" });
    check(r, 401);
    assert.equal(r.data.error.message, "账号或密码错误");
  }
  const limited = await api("/login", "POST", { username, password: "wrong" });
  check(limited, 429);
  assert.equal(limited.headers.get("retry-after"), "900");
});
test("13 idle expiry and logout revoke old token", async () => {
  await migration.execute(
    "UPDATE admin_sessions SET expires_at=DATE_SUB(UTC_TIMESTAMP(3),INTERVAL 1 SECOND) WHERE admin_id=(SELECT id FROM admins WHERE username=?)",
    [adminName],
  );
  check(await api("/me"), 401);
  cookie = checkLogin(
    await api("/login", "POST", { username: adminName, password }),
  );
  const old = cookie;
  check(await api("/logout", "POST", {}));
  cookie = old;
  check(await api("/me"), 401);
  cookie = checkLogin(
    await api("/login", "POST", { username: adminName, password }),
  );
});
function checkLogin(r: any) {
  check(r);
  return r.headers.get("set-cookie")!.split(";")[0];
}
test("14 application server restart preserves records and session", async () => {
  await new Promise<void>((r) => server.close(() => r()));
  server = app.listen(0, "127.0.0.1");
  await once(server, "listening");
  origin = `http://127.0.0.1:${server.address().port}`;
  check(await api("/me"));
  assert.equal(check(await api("/garments/" + A.id)).name, A.name);
  assert.equal(
    (await request("/t/" + TA.entry_code)).headers.get("location"),
    "/g/" + B.id,
  );
});
test("15 database outage returns safe 503 then recovers", async () => {
  execFileSync(
    "docker",
    ["compose", "-f", "compose.local.yaml", "stop", "mysql"],
    { stdio: "pipe" },
  );
  try {
    for (const path of [
      "/health",
      "/t/" + TA.entry_code,
      "/g/" + B.id,
      "/api/public/garments/" + B.id,
    ]) {
      const r = await request(path);
      check(r, 503);
      assert.equal(r.headers.get("cache-control"), "no-store");
      assert.doesNotMatch(r.text, /password|ECONNREFUSED|mysql:\/\//);
    }
  } finally {
    execFileSync(
      "docker",
      ["compose", "-f", "compose.local.yaml", "up", "-d", "--wait"],
      { stdio: "pipe" },
    );
  }
  check(await request("/health"));
  writeFileSync(
    ".local/browser.json",
    JSON.stringify({ username: adminName, password }),
    { mode: 0o600 },
  );
});

test('16 UTC session is enforced even when MySQL server defaults to Asia/Shanghai offset', async () => {
  const [{ zone }] = await rows('SELECT @@global.time_zone zone', [], migration);
  assert.match(zone, /^(SYSTEM|[+-]\d\d:\d\d)$/);
  rootSQL("SET GLOBAL time_zone='+08:00';");
  const fresh = poolFor(process.env.TEST_MIGRATION_URL!);
  try {
    const [result]: any = await fresh.query('SELECT @@session.time_zone zone, TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), CURRENT_TIMESTAMP()) offset_seconds');
    assert.equal(result[0].zone, '+00:00');
    assert.equal(result[0].offset_seconds, 0);
  } finally {
    await fresh.end();
    rootSQL("SET GLOBAL time_zone='" + zone + "';");
  }
});

test('17 ignored limiter insert failures are surfaced instead of crashing or bypassing rate limits', async () => {
  const username='constraint-test-'+randomUUID();
  const key=createHash('sha256').update(`127.0.0.1\0${username}`).digest('hex');
  const constraint='bumbum_test_limiter_insert_check';
  rootSQL(`ALTER TABLE bumbum_test.login_attempts ADD CONSTRAINT ${constraint} CHECK (attempt_key <> '${key}');`);
  const c=await migration.getConnection();
  try {
    // Reproduce the old query's behavior: INSERT IGNORE silently skips a rejected row.
    await c.execute('INSERT IGNORE INTO login_attempts VALUES (?,0,UTC_TIMESTAMP(3))',[key]);
    const [warnings]:any=await c.query('SHOW WARNINGS');
    assert.ok(warnings.some((w:any)=>w.Code===3819));
    const [absent]:any=await c.execute('SELECT * FROM login_attempts WHERE attempt_key=?',[key]);
    assert.equal(absent.length,0);
    const r=await api('/login','POST',{username,password:'virtual-wrong-password'});
    check(r,500);
    assert.equal(r.data.error.code,'ER_CHECK_CONSTRAINT_VIOLATED');
    assert.equal(r.headers.get('set-cookie'),null);
  } finally {
    c.release();
    rootSQL(`ALTER TABLE bumbum_test.login_attempts DROP CHECK ${constraint};`);
  }
});
