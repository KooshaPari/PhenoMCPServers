#!/usr/bin/env python3
# ruff: noqa: E501
"""Legacy browser monitor HTML for statusd."""

MONITOR_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent User Status</title>
<style>
:root {
  color-scheme: dark;
  --bg: #101114;
  --panel: rgba(24, 26, 31, 0.94);
  --line: rgba(255,255,255,0.14);
  --text: #f1f3f5;
  --muted: #a8afb8;
  --ok: #47d18c;
  --warn: #ffcf5b;
  --bad: #ff6b6b;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
  background:
    linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px),
    var(--bg);
  background-size: 48px 48px;
  color: var(--text);
  overflow: hidden;
}
#stage {
  position: fixed;
  inset: 0;
}
#eyeDot {
  position: absolute;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #fff, #7ee2b8 22%, #13b673 66%, #075e41);
  border: 2px solid rgba(255,255,255,0.84);
  box-shadow: 0 0 0 10px rgba(71,209,140,0.14), 0 0 42px rgba(71,209,140,0.55);
  transform: translate(-50%, -50%);
  left: 50%;
  top: 50%;
  transition: left 120ms linear, top 120ms linear, opacity 160ms ease;
}
#panel {
  position: fixed;
  top: 14px;
  right: 14px;
  width: min(390px, calc(100vw - 28px));
  max-height: calc(100vh - 28px);
  overflow: auto;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 18px 60px rgba(0,0,0,0.38);
  padding: 14px;
  backdrop-filter: blur(18px);
}
.row { display: flex; justify-content: space-between; gap: 16px; align-items: baseline; padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }
.row:last-child { border-bottom: 0; }
.k { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0; }
.v { font-size: 14px; text-align: right; overflow-wrap: anywhere; }
.status { display: flex; align-items: center; gap: 9px; font-size: 17px; font-weight: 650; margin-bottom: 10px; }
.led { width: 11px; height: 11px; border-radius: 50%; background: var(--warn); box-shadow: 0 0 16px currentColor; }
.led.active { background: var(--ok); color: var(--ok); }
.led.away { background: var(--bad); color: var(--bad); }
pre {
  margin: 10px 0 0;
  padding: 10px;
  border-radius: 6px;
  background: rgba(0,0,0,0.28);
  color: #d9dee5;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
button {
  appearance: none;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.08);
  color: var(--text);
  border-radius: 6px;
  padding: 7px 10px;
  font: inherit;
  font-size: 12px;
}
#controls { display: flex; gap: 8px; margin-top: 12px; }
</style>
</head>
<body>
<main id="stage" aria-label="Eye tracking monitor"><div id="eyeDot"></div></main>
<aside id="panel">
  <div class="status"><span id="led" class="led"></span><span id="statusText">loading</span></div>
  <div class="row"><span class="k">confidence</span><span id="confidence" class="v">-</span></div>
  <div class="row"><span class="k">eta</span><span id="eta" class="v">-</span></div>
  <div class="row"><span class="k">source</span><span id="source" class="v">-</span></div>
  <div class="row"><span class="k">eye state</span><span id="eyeState" class="v">-</span></div>
  <div class="row"><span class="k">screen</span><span id="screenPoint" class="v">-</span></div>
  <div class="row"><span class="k">updated</span><span id="updated" class="v">-</span></div>
  <div id="controls">
    <button id="center">Center</button>
    <button id="hide">Hide Dot</button>
    <button id="openPrivacy">Privacy</button>
  </div>
  <pre id="raw"></pre>
</aside>
<script>
const $ = (id) => document.getElementById(id);
let dotVisible = true;

function zoneToPoint(zone) {
  const map = {
    "top_left": [0.18, 0.18],
    "top": [0.5, 0.16],
    "top_right": [0.82, 0.18],
    "left": [0.18, 0.5],
    "center": [0.5, 0.5],
    "right": [0.82, 0.5],
    "bottom_left": [0.18, 0.82],
    "bottom": [0.5, 0.84],
    "bottom_right": [0.82, 0.82]
  };
  return map[zone] || map.center;
}

function setDot(eye) {
  const dot = $("eyeDot");
  let x = 0.5, y = 0.5;
  if (typeof eye.screen_x === "number" && typeof eye.screen_y === "number") {
    const sw = eye.screen_width || window.screen.width || window.innerWidth;
    const sh = eye.screen_height || window.screen.height || window.innerHeight;
    x = Math.max(0, Math.min(1, eye.screen_x / sw));
    y = Math.max(0, Math.min(1, eye.screen_y / sh));
  } else if (eye.screen_zone) {
    [x, y] = zoneToPoint(String(eye.screen_zone).replace("looking_at_screen:", ""));
  }
  dot.style.left = `${x * 100}%`;
  dot.style.top = `${y * 100}%`;
  dot.style.opacity = dotVisible && eye.fresh !== false ? "1" : "0.16";
}

async function getJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  return await response.json();
}

async function refresh() {
  const [statusWrap, dev] = await Promise.all([getJson("/status"), getJson("/dev/state")]);
  const status = statusWrap.data || statusWrap;
  const eye = dev.eye || {};
  $("statusText").textContent = status.status || "unknown";
  $("confidence").textContent = status.confidence ?? "-";
  $("eta").textContent = status.estimated_response || "-";
  $("source").textContent = status.source || "-";
  $("eyeState").textContent = eye.state || eye.screen_zone || "-";
  $("screenPoint").textContent = typeof eye.screen_x === "number" ? `${Math.round(eye.screen_x)}, ${Math.round(eye.screen_y)}` : (eye.screen_zone || "-");
  $("updated").textContent = eye.observed_at || "-";
  $("raw").textContent = JSON.stringify({ status, dev }, null, 2);
  const led = $("led");
  led.className = "led";
  if ((status.confidence || 0) >= 0.7) led.classList.add("active");
  if ((status.confidence || 0) <= 0.3) led.classList.add("away");
  setDot(eye);
}

$("center").onclick = async () => {
  await fetch("/dev/eye", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ screen_zone: "center", score: 0.7, state: "dev_center", max_age_seconds: 30 }) });
  refresh();
};
$("hide").onclick = () => {
  dotVisible = !dotVisible;
  $("hide").textContent = dotVisible ? "Hide Dot" : "Show Dot";
  refresh();
};
$("openPrivacy").onclick = () => window.open("/privacy", "_blank");

refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""
