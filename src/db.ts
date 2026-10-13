import mysql, { PoolConnection, RowDataPacket } from "mysql2/promise";
import { readFileSync } from "node:fs";
const prod = process.env.NODE_ENV === "production";
export function poolFor(url: string) {
  if (!url) throw new Error("DATABASE_URL is required");
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    throw new Error("DATABASE_URL must be a valid mysql URL");
  }
  if (u.protocol !== "mysql:") throw new Error("Use mysql URL");
  const tls = process.env.DB_TLS === "true";
  if (prod && !tls)
    throw new Error("Production requires DB_TLS=true and trusted CA");
  const pool = mysql.createPool({
    host: u.hostname,
    port: Number(u.port || 3306),
    user: decodeURIComponent(u.username),
    password: decodeURIComponent(u.password),
    database: u.pathname.slice(1),
    charset: "utf8mb4",
    timezone: "Z",
    connectionLimit: 5,
    connectTimeout: 5000,
    ssl: tls
      ? {
          ca: readFileSync(process.env.DB_CA_FILE || "/run/db-ca.pem", "utf8"),
          rejectUnauthorized: true,
          verifyIdentity: true,
        }
      : undefined,
    multipleStatements: false,
  });
  // Serialization timezone alone does not affect MySQL CURRENT_TIMESTAMP defaults.
  pool.pool.on("connection", (connection) => {
    connection.query("SET time_zone = '+00:00'", (error: Error | null) => {
      if (error) connection.destroy();
    });
  });
  return pool;
}
export const db = poolFor(process.env.DATABASE_URL || "");
export type Conn = PoolConnection;
export async function rows(
  sql: string,
  args: unknown[] = [],
  c: any = db,
): Promise<any[]> {
  const [r] = await c.execute(sql, args);
  return r as RowDataPacket[];
}
export async function tx<T>(fn: (c: Conn) => Promise<T>): Promise<T> {
  const c = await db.getConnection();
  try {
    await c.beginTransaction();
    const r = await fn(c);
    await c.commit();
    return r;
  } catch (e) {
    await c.rollback();
    throw e;
  } finally {
    c.release();
  }
}
