import { db, rows } from "./db.js";
import { hashPassword } from "./security.js";
import { randomUUID, createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { createInterface } from "node:readline/promises";
async function migrate() {
  const c = await db.getConnection();
  try {
    const locks = await rows(
      "SELECT GET_LOCK(CONCAT(DATABASE(), ':migration'),30) acquired",
      [],
      c,
    );
    if (locks[0].acquired !== 1) throw Error("Migration lock unavailable");
    await c.execute(
      "CREATE TABLE IF NOT EXISTS schema_migrations (name VARCHAR(100) PRIMARY KEY, checksum CHAR(64) NOT NULL, completed BOOLEAN NOT NULL DEFAULT FALSE) ENGINE=InnoDB",
    );
    for (const name of readdirSync("migrations")
      .filter((x) => x.endsWith(".sql"))
      .sort()) {
      const sql = readFileSync(`migrations/${name}`, "utf8"),
        checksum = createHash("sha256").update(sql).digest("hex");
      const old = await rows(
        "SELECT * FROM schema_migrations WHERE name=?",
        [name],
        c,
      );
      if (old.length) {
        if (old[0].checksum !== checksum || !old[0].completed)
          throw Error(
            "Changed or interrupted migration; inspect schema before repair",
          );
        continue;
      }
      await c.execute(
        "INSERT INTO schema_migrations(name,checksum) VALUES (?,?)",
        [name, checksum],
      );
      for (const statement of sql.split(";").filter((x) => x.trim()))
        await c.query(statement);
      await c.execute(
        "UPDATE schema_migrations SET completed=TRUE WHERE name=?",
        [name],
      );
      console.log("Applied", name);
    }
    console.log("Migrations complete");
  } finally {
    await c.query("SELECT RELEASE_LOCK(CONCAT(DATABASE(), ':migration'))");
    c.release();
  }
}
async function admin() {
  if (!process.stdin.isTTY)
    throw Error("Use an interactive terminal (docker compose run --rm tools)");
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const username = (await rl.question("管理员用户名: ")).trim();
  rl.close();
  async function secret(label: string) {
    process.stdout.write(label);
    process.stdin.setRawMode(true);
    process.stdin.resume();
    let value = "";
    return new Promise<string>((resolve, reject) => {
      const listener = (buf: Buffer) => {
        for (const ch of buf.toString()) {
          if (ch === "\u0003") {
            cleanup();
            reject(Error("Cancelled"));
            return;
          }
          if (ch === "\r" || ch === "\n") {
            cleanup();
            resolve(value);
            return;
          }
          if (ch === "\u007f") value = value.slice(0, -1);
          else if (ch >= " ") value += ch;
        }
      };
      function cleanup() {
        process.stdin.off("data", listener);
        process.stdin.setRawMode(false);
        process.stdin.pause();
        process.stdout.write("\n");
      }
      process.stdin.on("data", listener);
    });
  }
  const password = await secret("密码（不回显，至少12位）: "),
    confirm = await secret("再次输入: ");
  if (
    !username ||
    username.length > 100 ||
    password.length < 12 ||
    password.length > 128 ||
    password !== confirm
  )
    throw Error("Invalid username/password or confirmation");
  await db.execute(
    "INSERT INTO admins(id,username,password_hash) VALUES (?,?,?)",
    [randomUUID(), username, hashPassword(password)],
  );
  console.log("管理员创建成功");
}
try {
  if (process.argv[2] === "migrate") await migrate();
  else if (process.argv[2] === "admin") await admin();
  else throw Error("Usage: cli migrate|admin");
} catch (e: any) {
  console.error(
    e.code === "ER_DUP_ENTRY"
      ? "管理员已存在"
      : e.message?.includes("migration")
        ? e.message
        : "操作失败，请检查配置、权限和目标库",
  );
  process.exitCode = 1;
} finally {
  await db.end();
}
