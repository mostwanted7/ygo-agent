// Drive the web panel in headless Firefox (WebDriver BiDi, Node >= 22, nothing to install) through a list of steps
// and print one JSON report: every step's value, and every console message the page logged. The browser tests
// (tests/web/test_web_browser.py) use it; it works by hand too:
//
//   node tests/web/check.mjs URL steps.json
//
// steps.json: [{"wait": "JS expression", "timeout": ms}, {"eval": "JS expression"}, {"sleep": ms},
//              {"shot": "out.png"}, {"key": "Escape"}]. `wait` polls until the expression is truthy (and fails the
// step after `timeout`, default 30000); `eval` records the expression's value; `key` presses a key on the page.
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url, stepsFile, size = "1440x900"] = process.argv.slice(2);
const steps = JSON.parse(readFileSync(stepsFile, "utf8"));
const [width, height] = size.split("x").map(Number);
const port = 9300 + Math.floor(Math.random() * 600);
const profile = mkdtempSync(join(tmpdir(), "ygo-check-"));
writeFileSync(join(profile, "user.js"), 'user_pref("remote.active-protocols", 1);\n');
const firefox = spawn("firefox", ["--headless", "--no-remote", "--profile", profile, `--remote-debugging-port=${port}`,
  "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
let stderr = "";
firefox.stderr.on("data", (d) => { stderr += d; });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const report = { steps: [], console: [], ok: true };

let ws;
for (let i = 0; i < 120 && !ws; i++) {
  try {
    const w = new WebSocket(`ws://127.0.0.1:${port}/session`);
    await new Promise((res, rej) => { w.onopen = res; w.onerror = rej; });
    ws = w;
  } catch { await sleep(250); }
}
if (!ws) { console.log(JSON.stringify({ ok: false, error: "firefox did not start", stderr })); process.exit(1); }
let next = 1;
const pending = new Map();
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.method === "log.entryAdded") {
    report.console.push({ level: m.params.level, text: m.params.text });
    return;
  }
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
  await send("session.subscribe", { events: ["log.entryAdded"] });
  const context = (await send("browsingContext.getTree", {})).contexts[0].context;
  const evaluate = async (expression) => {
    const r = await send("script.evaluate", { expression: `(async () => (${expression}))()`, target: { context },
      awaitPromise: true, serializationOptions: { maxObjectDepth: 4 } });
    if (r.type === "exception") throw new Error(r.exceptionDetails.text);
    return unpack(r.result);
  };
  await send("browsingContext.setViewport", { context, viewport: { width, height } });
  await send("browsingContext.navigate", { context, url, wait: "complete" });
  for (const step of steps) {
    const out = { ...step };
    try {
      if (step.wait) {
        const t0 = Date.now();
        let v = false;
        while (!(v = await evaluate(step.wait).catch(() => false)) && Date.now() - t0 < (step.timeout ?? 30000)) await sleep(150);
        out.value = v;
        if (!v) throw new Error("timed out waiting");
      } else if (step.eval) out.value = await evaluate(step.eval);
      else if (step.sleep) await sleep(step.sleep);
      else if (step.key) {
        const value = { Escape: "", End: "", ArrowLeft: "", ArrowRight: "", Home: "" }[step.key] ?? step.key;
        await send("input.performActions", { context, actions: [{ type: "key", id: "kb", actions: [
          { type: "keyDown", value }, { type: "keyUp", value }] }] });
      } else if (step.shot) {
        const { data } = await send("browsingContext.captureScreenshot", { context });
        writeFileSync(step.shot, Buffer.from(data, "base64"));
      }
    } catch (e) {
      out.error = String(e.message || e);
      report.ok = false;
    }
    report.steps.push(out);
    if (out.error) break;
  }
} finally {
  console.log(JSON.stringify(report));
  ws.close();
  firefox.kill("SIGTERM");
  await sleep(500);
  rmSync(profile, { recursive: true, force: true });
}

function unpack(v) {
  if (!v) return v;
  switch (v.type) {
    case "undefined": case "null": return null;
    case "string": case "number": case "boolean": return v.value;
    case "array": return (v.value || []).map(unpack);
    case "object": return Object.fromEntries((v.value || []).map(([k, x]) => [typeof k === "string" ? k : unpack(k), unpack(x)]));
    default: return v.value ?? v.type;
  }
}
