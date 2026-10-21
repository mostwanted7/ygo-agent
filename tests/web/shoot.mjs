// Screenshots of the web panel with headless Firefox, over WebDriver BiDi. Needs only `firefox` and Node >= 22
// (its built-in WebSocket); nothing to install. Used for docs/img/ and for recording frames for a GIF.
//
//   node tests/web/shoot.mjs URL OUT.png [1440x900]       one screenshot, once the panel shows a decision
//   node tests/web/shoot.mjs jobs.json                    several, in one browser session
//
// jobs.json: [{"url", "out", "width", "height", "wait": "JS expression", "eval": "JS run before the shot",
//              "delay": ms, "frames": N, "every": ms}]. A job without "url" stays on the current page. With "frames",
// OUT may contain %03d and N screenshots are taken `every` ms apart (e.g. a live demo; then ffmpeg makes the GIF).
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [arg, out, size = "1440x900"] = process.argv.slice(2);
if (!arg) {
  console.error("usage: node tests/web/shoot.mjs URL OUT.png [WxH] | jobs.json");
  process.exit(2);
}
const [w, h] = size.split("x").map(Number);
const jobs = arg.endsWith(".json") ? JSON.parse(readFileSync(arg, "utf8"))
  : [{ url: arg, out, width: w, height: h, wait: "document.querySelector('#stream .dc')", delay: 1200 }];

const port = 9300 + Math.floor(Math.random() * 600);
const profile = mkdtempSync(join(tmpdir(), "ygo-shoot-"));
writeFileSync(join(profile, "user.js"), 'user_pref("remote.active-protocols", 1);\n');
const firefox = spawn("firefox", ["--headless", "--no-remote", "--profile", profile, `--remote-debugging-port=${port}`, "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] });
let stderr = "";
firefox.stderr.on("data", (d) => { stderr += d; });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function connect() {
  for (let i = 0; i < 80; i++) {
    try {
      const ws = new WebSocket(`ws://127.0.0.1:${port}/session`);
      await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
      return ws;
    } catch { await sleep(250); }
  }
  throw new Error(`firefox did not open its WebDriver BiDi port\n${stderr}`);
}

const ws = await connect();
let next = 1;
const pending = new Map();
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  const p = m.id && pending.get(m.id);
  if (!p) return;
  pending.delete(m.id);
  m.type === "error" ? p.rej(new Error(`${m.error}: ${m.message}`)) : p.res(m.result);
};
const send = (method, params = {}) => new Promise((res, rej) => {
  const id = next++;
  pending.set(id, { res, rej });
  ws.send(JSON.stringify({ id, method, params }));
});

try {
  await send("session.new", { capabilities: {} });
  const context = (await send("browsingContext.getTree", {})).contexts[0].context;
  const evaluate = async (expression) =>
    (await send("script.evaluate", { expression, target: { context }, awaitPromise: true })).result?.value;
  const shot = async (path) => {
    const { data } = await send("browsingContext.captureScreenshot", { context });
    writeFileSync(path, Buffer.from(data, "base64"));
  };
  for (const job of jobs) {
    await send("browsingContext.setViewport", { context, viewport: { width: job.width || 1440, height: job.height || 900 } });
    if (job.url) await send("browsingContext.navigate", { context, url: job.url, wait: "complete" });
    if (job.wait) for (let i = 0; i < 100 && !(await evaluate(`!!(${job.wait})`)); i++) await sleep(150);
    if (job.eval) await evaluate(`(async () => { ${job.eval} })()`);
    await sleep(job.delay ?? 900);
    if (job.frames) {
      for (let i = 0; i < job.frames; i++) {
        const t = Date.now();
        await shot(job.out.replace("%03d", String(i).padStart(3, "0")));
        await sleep(Math.max(0, (job.every ?? 200) - (Date.now() - t)));
      }
      console.log(`saved ${job.frames} frames: ${job.out}`);
    } else {
      await shot(job.out);
      console.log(`saved ${job.out}`);
    }
  }
} finally {
  ws.close();
  firefox.kill("SIGTERM");
  await sleep(600);
  rmSync(profile, { recursive: true, force: true });
}
