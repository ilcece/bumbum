import { app } from "./app.js";
import { db } from "./db.js";
const server = app.listen(Number(process.env.PORT || 3000), "0.0.0.0", () =>
  console.log("bumbum listening"),
);
async function stop() {
  server.close(async () => {
    await db.end();
    process.exit(0);
  });
  setTimeout(() => process.exit(1), 10000).unref();
}
process.on("SIGTERM", stop);
process.on("SIGINT", stop);
