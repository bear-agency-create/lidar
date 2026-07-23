#!/usr/bin/env python3
"""Лидар-карта: режим DRIVE — поза из /odom (Arduino), опционально CSM; телеоп с веб-пульта."""

from __future__ import annotations

import json
import logging
import math
import heapq
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan

SCAN_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
)

ODOM_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
)

PORT = 8765
HOST = "0.0.0.0"

MIN_RANGE_SHOW = 0.05
MIN_RANGE_MAP = 0.10  # catch chair legs close-in
MAX_RANGE = 12.0

MAP_SIZE_M = 40.0
MAP_RES = 0.05  # finer grid — thin legs + smoother pouf edges
MAP_CELLS = int(MAP_SIZE_M / MAP_RES)

MAP_PATH = Path(
    os.path.expanduser("~/robot_nav/maps/remembered_occupancy.json")
)
LOG_PATH = Path(os.path.expanduser("~/robot_nav/logs/lidar_map.log"))
AUTOSAVE_SEC = 5.0

# Robot footprint (mecanum chassis ≈ 0.82×0.56 m + margin)
ROBOT_LENGTH_M = 0.85
ROBOT_WIDTH_M = 0.58
ROBOT_RADIUS_M = 0.48  # circumscribed radius for planning clearance

# Correlative scan-to-map (опциональное уточнение позы / fallback без odom).
ICP_MAX_DIST = 0.55
ICP_ITERS = 10
ICP_STRIDE = 2
ICP_MAX_POINTS = 120
MAP_HIT_STRIDE = 1  # every beam → thin legs visible
CSM_YAW_SPAN = math.radians(50.0)
CSM_YAW_STEP = math.radians(3.0)
CSM_XY_SPAN = 0.22
CSM_XY_STEP = 0.11
MIN_MATCH_SCORE = 0.22
MIN_MATCHES_ICP = 30
CSM_REFINE_YAW_SPAN = math.radians(12.0)
CSM_REFINE_YAW_STEP = math.radians(2.0)
CSM_REFINE_XY_SPAN = 0.12
CSM_REFINE_XY_STEP = 0.06
MIN_REFINE_SCORE = 0.35

CMD_VX_MAX = 0.55
CMD_VY_MAX = 0.45
CMD_W_MAX = 1.4
CMD_WATCHDOG_SEC = 0.25
CMD_FILE = Path("/tmp/robot_cmd.json")
ODOM_STALE_SEC = 1.0

# Temporary people obstacles (not written into static map).
TEMP_TTL_SEC = 2.0
TEMP_CELL_VAL = 50  # UI: orange
TEMP_INFLATE = max(2, int(round(0.12 / MAP_RES)))
NAV_ROBOT_R = max(3, int(math.ceil(ROBOT_RADIUS_M / MAP_RES)))
NAV_GOAL_TOL = 0.28
NAV_VX = 0.28
NAV_W_MAX = 0.9
HIT_BLOB = 1  # soft inflate hits so thin legs become visible cells
OCC_DISPLAY = 0.55  # show weak occupied (legs) earlier
OCC_SOLID = 1.0


def _setup_file_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("lidar_map")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(sh)
    return log


FILE_LOG = _setup_file_logger()

HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>лидар — езда</title>
<style>
  html, body { margin:0; height:100%; background:#111; color:#ddd; font:13px monospace; }
  #bar { padding:6px 10px; background:#1a1a1a; border-bottom:1px solid #333; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
  button { font:12px monospace; background:#222; color:#ddd; border:1px solid #555; padding:3px 8px; cursor:pointer; }
  button.on { background:#345; border-color:#79a; }
  button.save { border-color:#5a5; color:#afa; }
  button.again { border-color:#a85; color:#fda; }
  #stage { position:absolute; inset:32px 0 0 0; }
  canvas { width:100%; height:100%; display:block; background:#000; cursor:crosshair; }
  #legend {
    position:absolute; left:10px; bottom:10px; background:rgba(0,0,0,0.82);
    border:1px solid #444; padding:8px 10px; line-height:1.5; max-width:460px;
    pointer-events:none;
  }
  #legend b { color:#fff; }
  .sw { display:inline-block; width:10px; height:10px; margin-right:6px; vertical-align:middle; }
  #warn { color:#fa4; }
  #pad {
    position:absolute; right:12px; bottom:12px; display:grid;
    grid-template-columns: repeat(3, 52px); grid-template-rows: repeat(4, 48px);
    gap:6px; z-index:5; user-select:none; -webkit-user-select:none;
  }
  #pad button {
    font:18px monospace; background:#1c1c1c; color:#eee; border:1px solid #666;
    border-radius:6px; padding:0; touch-action:none;
  }
  #pad button:active, #pad button.held { background:#356; border-color:#8cf; }
  #pad button.stop { grid-column: 2; background:#311; border-color:#a44; color:#faa; }
  #pad .empty { visibility:hidden; pointer-events:none; }
</style>
</head>
<body>
<div id="bar">
  <button id="bScan" class="on">скан сейчас</button>
  <button id="bMap" class="on">память стен</button>
  <button id="bFollow" class="on">следить</button>
  <button id="bSave" class="save">сохранить</button>
  <button id="bFreeze" class="save">заморозить комнату</button>
  <button id="bAgain" class="again">заново</button>
  <span id="info">—</span>
</div>
<div id="stage">
  <canvas id="c"></canvas>
  <div id="pad" aria-label="пульт">
    <button type="button" data-cmd="strafe_l" title="бок влево (Z, после прошивки mecanum)">Ｚ</button>
    <button type="button" data-cmd="fwd" title="вперёд (W)">▲</button>
    <button type="button" data-cmd="strafe_r" title="бок вправо (C, после прошивки mecanum)">Ｃ</button>
    <button type="button" data-cmd="left" title="поворот влево (Q)">◀</button>
    <button type="button" class="empty" tabindex="-1" aria-hidden="true"></button>
    <button type="button" data-cmd="right" title="поворот вправо (E)">▶</button>
    <span class="empty"></span>
    <button type="button" data-cmd="back" title="назад (S)">▼</button>
    <span class="empty"></span>
    <span class="empty"></span>
    <button type="button" class="stop" data-cmd="stop" title="стоп (Space)">■</button>
    <span class="empty"></span>
  </div>
  <div id="legend">
    <div><b>Режим:</b> пульт → Arduino моторы. Карта с <b>/odom</b> + лидар. Лидар на роботе.</div>
    <div>W/S вперёд-назад · A/D или ＺＣ боком · Q/E или ◀▶ поворот · Space стоп</div>
    <div>Кликни по странице, потом держи клавиши или кнопки. Отпустил — стоп.</div>
    <div>Меканум X: 4 направления. Enable задних на D5/D6 (общие) — боковой ход приближённый.</div>
    <div><b>заново</b> — сброс. <b>заморозить комнату</b> — стены навечно; люди = оранжевые временно.</div>
    <div>После заморозки клик по карте = ехать туда, объезжая людей (в карту стен не пишет).</div>
    <div><span class="sw" style="background:#f44"></span><b>красные</b> — лидар сейчас</div>
    <div><span class="sw" style="background:#eee;border:1px solid #777"></span><b>белое</b> — стена / мебель</div>
    <div><span class="sw" style="background:#fa0"></span><b>оранж</b> — человек / временно</div>
    <div><span class="sw" style="background:#777"></span><b>серое</b> — пустое</div>
    <div><span class="sw" style="background:#0f0"></span><b>зелёный</b> — робот (реальный размер) · <span class="sw" style="background:#0ff"></span>путь</div>
  </div>
</div>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
let showScan = true, showMap = true, follow = true;
let scale = 35;
let data = null;
let panX = 0, panY = 0;
let drag = null;
let mapFrozen = false;

const VX = 0.45, VY = 0.35, W = 1.2;
const CMDS = {
  fwd:  {vx: VX,  vy: 0,   w: 0},
  back: {vx:-VX,  vy: 0,   w: 0},
  left: {vx: 0,   vy: 0,   w: W},
  right:{vx: 0,   vy: 0,   w:-W},
  strafe_l:{vx: 0, vy: VY,  w: 0},
  strafe_r:{vx: 0, vy:-VY,  w: 0},
  yaw_l:{vx: 0,   vy: 0,   w: W},
  yaw_r:{vx: 0,   vy: 0,   w:-W},
  stop: {vx: 0,   vy: 0,   w: 0},
};

const held = new Set();
let driveTimer = null;

async function postCmd(body) {
  try {
    await fetch('/api/cmd', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
      cache: 'no-store',
    });
  } catch (_) {}
}

async function postStop() {
  try {
    await fetch('/api/cmd/stop', {method:'POST', cache:'no-store'});
  } catch (_) {}
}

function mergedCmd() {
  let vx = 0, vy = 0, w = 0;
  for (const name of held) {
    const c = CMDS[name];
    if (!c) continue;
    vx += c.vx; vy += c.vy; w += c.w;
  }
  const clamp = (v, m) => Math.max(-m, Math.min(m, v));
  return {vx: clamp(vx, 0.35), vy: clamp(vy, 0.35), w: clamp(w, 1.2)};
}

function refreshDriveLoop() {
  if (held.size === 0) {
    if (driveTimer) { clearInterval(driveTimer); driveTimer = null; }
    postStop();
    return;
  }
  const send = () => postCmd(mergedCmd());
  send();
  if (!driveTimer) driveTimer = setInterval(send, 80);
}

function holdStart(name) {
  if (!CMDS[name]) return;
  if (name === 'stop') {
    held.clear();
    document.querySelectorAll('#pad button.held').forEach(b => b.classList.remove('held'));
    refreshDriveLoop();
    return;
  }
  held.add(name);
  const btn = document.querySelector('#pad button[data-cmd="'+name+'"]');
  if (btn) btn.classList.add('held');
  refreshDriveLoop();
}

function holdEnd(name) {
  if (!name || name === 'stop') return;
  held.delete(name);
  const btn = document.querySelector('#pad button[data-cmd="'+name+'"]');
  if (btn) btn.classList.remove('held');
  refreshDriveLoop();
}

function allStop() {
  held.clear();
  document.querySelectorAll('#pad button.held').forEach(b => b.classList.remove('held'));
  if (driveTimer) { clearInterval(driveTimer); driveTimer = null; }
  postStop();
}

document.querySelectorAll('#pad button[data-cmd]').forEach((btn) => {
  const name = btn.getAttribute('data-cmd');
  const down = (e) => { e.preventDefault(); try { btn.setPointerCapture(e.pointerId); } catch(_){} holdStart(name); };
  const up = (e) => { e.preventDefault(); holdEnd(name); };
  btn.addEventListener('pointerdown', down);
  btn.addEventListener('pointerup', up);
  btn.addEventListener('pointercancel', up);
  btn.addEventListener('lostpointercapture', up);
});

window.addEventListener('blur', allStop);
document.addEventListener('visibilitychange', () => { if (document.hidden) allStop(); });

const KEY_MAP = {
  KeyW: 'fwd', ArrowUp: 'fwd',
  KeyS: 'back', ArrowDown: 'back',
  KeyA: 'strafe_l', ArrowLeft: 'strafe_l',
  KeyD: 'strafe_r', ArrowRight: 'strafe_r',
  KeyQ: 'yaw_l',
  KeyE: 'yaw_r',
  KeyZ: 'strafe_l',
  KeyC: 'strafe_r',
  Space: 'stop',
};

window.addEventListener('keydown', (e) => {
  if (e.repeat) return;
  const name = KEY_MAP[e.code];
  if (!name) return;
  e.preventDefault();
  holdStart(name);
});
window.addEventListener('keyup', (e) => {
  const name = KEY_MAP[e.code];
  if (!name || name === 'stop') return;
  e.preventDefault();
  holdEnd(name);
});

document.getElementById('bScan').onclick = (e) => {
  showScan = !showScan; e.target.classList.toggle('on', showScan); draw();
};
document.getElementById('bMap').onclick = (e) => {
  showMap = !showMap; e.target.classList.toggle('on', showMap); draw();
};
document.getElementById('bFollow').onclick = (e) => {
  follow = !follow; e.target.classList.toggle('on', follow); draw();
};
document.getElementById('bSave').onclick = async () => {
  const r = await fetch('/api/save', {method:'POST'});
  const j = await r.json();
  document.getElementById('info').textContent = j.ok
    ? ('сохранено: ' + (j.path || '') + ' | стен ' + (j.hits || 0))
    : ('ошибка сохранения');
};
document.getElementById('bAgain').onclick = async () => {
  if (!confirm('Начать карту заново? Старые стены сотрутся, центр вокруг текущей позиции.')) return;
  const r = await fetch('/api/clear', {method:'POST'});
  const j = await r.json().catch(() => ({ok:true, frozen:false}));
  mapFrozen = false;
  const bf = document.getElementById('bFreeze');
  if (bf) { bf.textContent = 'заморозить комнату'; bf.classList.add('save'); bf.classList.remove('again'); }
  document.getElementById('info').textContent = j.ok
    ? 'сброшено — запись стен ВКЛ, едь с пульта'
    : ('ошибка сброса: ' + (j.error || ''));
};
document.getElementById('bFreeze').onclick = async () => {
  const r = await fetch('/api/freeze', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({frozen: !mapFrozen}),
  });
  const j = await r.json().catch(() => ({ok:false}));
  if (!j.ok) {
    document.getElementById('info').textContent = 'freeze error: ' + (j.error || '');
    return;
  }
  mapFrozen = !!j.frozen;
  const bf = document.getElementById('bFreeze');
  bf.textContent = mapFrozen ? 'писать стены снова' : 'заморозить комнату';
  bf.classList.toggle('save', !mapFrozen);
  bf.classList.toggle('again', mapFrozen);
  document.getElementById('info').textContent = mapFrozen
    ? 'комната заморожена — люди будут оранжевыми; клик = цель объезда'
    : 'запись стен снова включена';
};

canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  scale = Math.min(200, Math.max(8, scale * (e.deltaY > 0 ? 0.9 : 1.1)));
  draw();
}, {passive:false});

canvas.addEventListener('pointerdown', (e) => {
  if (follow && !mapFrozen) return;
  if (mapFrozen && !e.shiftKey) {
    // Click = navigate to world point (avoid people)
    const r = canvas.parentElement.getBoundingClientRect();
    const cx = r.width/2, cy = r.height/2;
    const pose = (data && data.pose) || {x:0,y:0};
    const viewX = follow ? pose.x : panX;
    const viewY = follow ? pose.y : panY;
    const sx = e.clientX - r.left;
    const sy = e.clientY - r.top;
    // inverse of worldToScreen: [cx - (wy-oy)*s, cy - (wx-ox)*s]
    const wx = viewX - (sy - cy) / scale;
    const wy = viewY - (sx - cx) / scale;
    fetch('/api/goal', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({x: wx, y: wy}),
    }).then(r => r.json()).then(j => {
      document.getElementById('info').textContent = j.ok
        ? ('цель (' + wx.toFixed(1) + ',' + wy.toFixed(1) + ') путь ' + (j.path_len||0))
        : ('нет пути: ' + (j.error || ''));
    }).catch(() => {});
    return;
  }
  if (follow) return;
  drag = {x: e.clientX, y: e.clientY, panX, panY};
  canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener('pointermove', (e) => {
  if (!drag) return;
  panX = drag.panX + (e.clientY - drag.y) / scale;
  panY = drag.panY - (e.clientX - drag.x) / scale;
  draw();
});
canvas.addEventListener('pointerup', () => { drag = null; });

function resize() {
  const dpr = devicePixelRatio || 1;
  const r = canvas.parentElement.getBoundingClientRect();
  canvas.width = Math.floor(r.width * dpr);
  canvas.height = Math.floor(r.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}
window.addEventListener('resize', resize);

function worldToScreen(wx, wy, cx, cy, ox, oy) {
  return [cx - (wy - oy) * scale, cy - (wx - ox) * scale];
}

function draw() {
  const r = canvas.parentElement.getBoundingClientRect();
  const w = r.width, h = r.height;
  const cx = w/2, cy = h/2;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, w, h);

  const pose = (data && data.pose) || {x:0,y:0,yaw:0,ok:false};
  const viewX = follow ? pose.x : panX;
  const viewY = follow ? pose.y : panY;

  ctx.strokeStyle = '#222';
  ctx.lineWidth = 1;
  const meters = Math.ceil(Math.max(w,h)/(2*scale)) + 2;
  const gx0 = Math.floor(viewX - meters);
  const gy0 = Math.floor(viewY - meters);
  for (let i = gx0; i <= gx0 + 2*meters; i++) {
    const [x0,y0] = worldToScreen(i, viewY - meters, cx, cy, viewX, viewY);
    const [x1,y1] = worldToScreen(i, viewY + meters, cx, cy, viewX, viewY);
    ctx.beginPath(); ctx.moveTo(x0,y0); ctx.lineTo(x1,y1); ctx.stroke();
  }
  for (let j = gy0; j <= gy0 + 2*meters; j++) {
    const [x0,y0] = worldToScreen(viewX - meters, j, cx, cy, viewX, viewY);
    const [x1,y1] = worldToScreen(viewX + meters, j, cx, cy, viewX, viewY);
    ctx.beginPath(); ctx.moveTo(x0,y0); ctx.lineTo(x1,y1); ctx.stroke();
  }

  if (!data) return;

  if (showMap && data.map && data.map.cells) {
    const m = data.map;
    const res = m.resolution;
    const origin = m.origin;
    const s = Math.max(1.2, res * scale + 0.5);
    ctx.fillStyle = 'rgba(90,90,90,0.45)';
    for (const cell of m.cells) {
      if (cell[2] !== 0) continue;
      const wx = origin[0] + (cell[0] + 0.5) * res;
      const wy = origin[1] + (cell[1] + 0.5) * res;
      const [x,y] = worldToScreen(wx, wy, cx, cy, viewX, viewY);
      ctx.fillRect(x - s/2, y - s/2, s, s);
    }
    // Solid furniture/walls — soft fill + bright edge for cleaner pouf borders
    for (const cell of m.cells) {
      if (cell[2] !== 100 && cell[2] !== 90) continue;
      const wx = origin[0] + (cell[0] + 0.5) * res;
      const wy = origin[1] + (cell[1] + 0.5) * res;
      const [x,y] = worldToScreen(wx, wy, cx, cy, viewX, viewY);
      ctx.fillStyle = cell[2] === 90 ? 'rgba(220,220,220,0.75)' : '#e8e8e8';
      ctx.fillRect(x - s/2, y - s/2, s + 0.4, s + 0.4);
    }
    ctx.fillStyle = '#fa0';
    for (const cell of m.cells) {
      if (cell[2] !== 50) continue;
      const wx = origin[0] + (cell[0] + 0.5) * res;
      const wy = origin[1] + (cell[1] + 0.5) * res;
      const [x,y] = worldToScreen(wx, wy, cx, cy, viewX, viewY);
      ctx.fillRect(x - s/2, y - s/2, s + 0.5, s + 0.5);
    }
  }

  if (data.path && data.path.length > 1) {
    ctx.strokeStyle = '#0cf';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < data.path.length; i++) {
      const [x,y] = worldToScreen(data.path[i][0], data.path[i][1], cx, cy, viewX, viewY);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  if (data.goal) {
    const [gx, gy] = worldToScreen(data.goal[0], data.goal[1], cx, cy, viewX, viewY);
    ctx.strokeStyle = '#ff0';
    ctx.beginPath();
    ctx.arc(gx, gy, 8, 0, Math.PI*2);
    ctx.stroke();
  }

  if (showScan && data.points) {
    ctx.fillStyle = '#f44';
    for (const p of data.points) {
      const [x,y] = worldToScreen(p.x, p.y, cx, cy, viewX, viewY);
      ctx.fillRect(x - 1.5, y - 1.5, 3, 3);
    }
  }

  const [rx, ry] = worldToScreen(pose.x, pose.y, cx, cy, viewX, viewY);
  const yaw = pose.yaw || 0;
  const bot = data.robot || {length: 0.85, width: 0.58, radius: 0.48};
  // Footprint (robot size) — rotated rectangle + clearance circle
  ctx.save();
  ctx.translate(rx, ry);
  ctx.rotate(-yaw);
  const fl = (bot.length || 0.85) * scale;
  const fw = (bot.width || 0.58) * scale;
  const fr = (bot.radius || 0.48) * scale;
  ctx.beginPath();
  ctx.ellipse(0, 0, fr, fr, 0, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(0,255,120,0.35)';
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.fillStyle = pose.ok ? 'rgba(0,220,80,0.35)' : 'rgba(255,170,0,0.35)';
  ctx.fillRect(-fw/2, -fl/2, fw, fl);
  ctx.strokeStyle = pose.ok ? '#0f0' : '#fa0';
  ctx.lineWidth = 2;
  ctx.strokeRect(-fw/2, -fl/2, fw, fl);
  ctx.beginPath();
  ctx.moveTo(0, -fl/2);
  ctx.lineTo(6, -fl/2 + 12);
  ctx.lineTo(-6, -fl/2 + 12);
  ctx.closePath();
  ctx.fillStyle = pose.ok ? '#0f0' : '#fa0';
  ctx.fill();
  ctx.restore();
}

async function tick() {
  try {
    const res = await fetch('/api/scan', {cache:'no-store'});
    data = await res.json();
    if (data.ok) {
      const p = data.pose || {};
      const hits = data.map ? data.map.hits : 0;
      const yawDeg = ((p.yaw || 0) * 180 / Math.PI);
      const saved = data.saved_ago != null ? (' | память ' + data.saved_ago + 'с назад') : '';
      const odomTxt = data.odom_ok ? 'odom ok' : 'odom нет';
      let warn = '';
      if (data.stale) warn += ' | ' + (data.error || 'лидар молчит');
      if (!data.odom_ok) warn += ' | поза по скану (fallback)';
      if (data.mapping === false) warn += ' | матч слабый — стены не пишу';
      const sc = (data.score != null) ? (' | матч ' + Number(data.score).toFixed(2)) : '';
      const frozen = data.frozen ? ' | КОМНАТА ЗАМОРОЖЕНА' : '';
      const people = (data.temp_hits != null) ? (' | люди ' + data.temp_hits) : '';
      document.getElementById('info').innerHTML =
        `еду с пульта | стен ${hits} | x=${(p.x||0).toFixed(2)} y=${(p.y||0).toFixed(2)} yaw=${yawDeg.toFixed(0)}° | ${odomTxt}` +
        sc + saved + frozen + people + (warn ? (' <span id="warn">' + warn + '</span>') : '');
      if (typeof data.frozen === 'boolean' && data.frozen !== mapFrozen) {
        mapFrozen = data.frozen;
        const bf = document.getElementById('bFreeze');
        if (bf) {
          bf.textContent = mapFrozen ? 'писать стены снова' : 'заморозить комнату';
          bf.classList.toggle('save', !mapFrozen);
          bf.classList.toggle('again', mapFrozen);
        }
      }
      draw();
    } else {
      document.getElementById('info').textContent = data.error || 'нет данных';
    }
  } catch (e) {
    document.getElementById('info').textContent = 'нет связи — открой http://0.0.0.0:8765/';
  }
  setTimeout(tick, 100);
}
resize();
tick();
</script>
</body>
</html>
"""


def _wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _yaw_from_quat(qx: float, qy: float, qz: float, qw: float) -> float:
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def _transform_local(pts: np.ndarray, x: float, y: float, yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    out = np.empty_like(pts)
    out[:, 0] = x + c * pts[:, 0] - s * pts[:, 1]
    out[:, 1] = y + s * pts[:, 0] + c * pts[:, 1]
    return out


def _icp_refine_pose(
    local: np.ndarray,
    ref_world: np.ndarray,
    x: float,
    y: float,
    yaw: float,
) -> tuple[float, float, float, int]:
    """Refine pose so local points match ref_world. Returns x,y,yaw,matches."""
    if local.shape[0] < 25 or ref_world.shape[0] < 25:
        return x, y, yaw, 0
    matches = 0
    for _ in range(ICP_ITERS):
        src = _transform_local(local, x, y, yaw)
        d2 = np.sum((src[:, None, :] - ref_world[None, :, :]) ** 2, axis=2)
        idx = np.argmin(d2, axis=1)
        mind = d2[np.arange(len(src)), idx]
        mask = mind < (ICP_MAX_DIST * ICP_MAX_DIST)
        matches = int(mask.sum())
        if matches < 20:
            break
        a = src[mask]
        b = ref_world[idx[mask]]
        ca = a.mean(axis=0)
        cb = b.mean(axis=0)
        aa = a - ca
        bb = b - cb
        h = aa.T @ bb
        u, _, vt = np.linalg.svd(h)
        r = vt.T @ u.T
        if np.linalg.det(r) < 0:
            vt = vt.copy()
            vt[-1, :] *= -1.0
            r = vt.T @ u.T
        t = cb - r @ ca
        c, s = math.cos(yaw), math.sin(yaw)
        r_pose = np.array([[c, -s], [s, c]], dtype=np.float64)
        r_new = r @ r_pose
        yaw = math.atan2(r_new[1, 0], r_new[0, 0])
        xy = r @ np.array([x, y], dtype=np.float64) + t
        x, y = float(xy[0]), float(xy[1])
    return x, y, yaw, matches


def _score_against_ref(world: np.ndarray, ref: np.ndarray) -> float:
    if world.shape[0] == 0 or ref.shape[0] == 0:
        return 0.0
    if ref.shape[0] > 220:
        ref = ref[:: max(1, ref.shape[0] // 220)]
    d2 = np.sum((world[:, None, :] - ref[None, :, :]) ** 2, axis=2)
    mind = np.min(d2, axis=1)
    good = mind < (0.35 * 0.35)
    if good.size == 0:
        return 0.0
    return float(np.mean(good))


def _correlative_search(
    local: np.ndarray,
    ref: np.ndarray,
    x: float,
    y: float,
    yaw: float,
    score_fn=None,
    yaw_span: float = CSM_YAW_SPAN,
    yaw_step: float = CSM_YAW_STEP,
    xy_span: float = CSM_XY_SPAN,
    xy_step: float = CSM_XY_STEP,
) -> tuple[float, float, float, float]:
    """Yaw/xy grid search (Cartographer-style CSM lite), then ICP refine."""
    best_score = -1.0
    bx, by, byaw = x, y, yaw
    yaw_vals = np.arange(-yaw_span, yaw_span + 1e-9, yaw_step)
    xy_vals = np.arange(-xy_span, xy_span + 1e-9, xy_step)
    step = max(1, local.shape[0] // 50)
    coarse = local[::step]

    def eval_pose(px: float, py: float, pyaw: float) -> float:
        ww = _transform_local(coarse, px, py, pyaw)
        if score_fn is not None:
            return float(score_fn(ww))
        return _score_against_ref(ww, ref)

    for dyaw in yaw_vals:
        yy = _wrap_angle(yaw + float(dyaw))
        for dx in xy_vals:
            for dy in xy_vals:
                sc = eval_pose(x + float(dx), y + float(dy), yy)
                if sc > best_score:
                    best_score = sc
                    bx, by, byaw = x + float(dx), y + float(dy), yy
    nx, ny, nyaw, matches = _icp_refine_pose(local, ref, bx, by, byaw)
    world = _transform_local(local, nx, ny, nyaw)
    if score_fn is not None:
        score = float(score_fn(world))
    else:
        score = _score_against_ref(world, ref)
    if matches < MIN_MATCHES_ICP:
        score *= 0.5
    return nx, ny, nyaw, score


class OccupancyMap:
    def __init__(self) -> None:
        self.res = MAP_RES
        self.w = MAP_CELLS
        self.h = MAP_CELLS
        self.origin_x = -MAP_SIZE_M / 2.0
        self.origin_y = -MAP_SIZE_M / 2.0
        self.logodds = [0.0] * (self.w * self.h)
        self.lock = threading.Lock()
        self.dirty = False
        self.last_save = 0.0

    def clear(self) -> None:
        with self.lock:
            self.logodds = [0.0] * (self.w * self.h)
            self.dirty = True

    def recentre(self, x: float, y: float) -> None:
        with self.lock:
            self.origin_x = x - MAP_SIZE_M / 2.0
            self.origin_y = y - MAP_SIZE_M / 2.0
            self.logodds = [0.0] * (self.w * self.h)
            self.dirty = True

    def _idx(self, ix: int, iy: int) -> int | None:
        if 0 <= ix < self.w and 0 <= iy < self.h:
            return iy * self.w + ix
        return None

    def _world_to_cell(self, x: float, y: float) -> tuple[int, int]:
        ix = int((x - self.origin_x) / self.res)
        iy = int((y - self.origin_y) / self.res)
        return ix, iy

    def integrate(
        self, ox: float, oy: float, hits: list[tuple[float, float]]
    ) -> None:
        with self.lock:
            sx, sy = self._world_to_cell(ox, oy)
            touched: list[tuple[int, int]] = []
            for hx, hy in hits:
                ex, ey = self._world_to_cell(hx, hy)
                for cx, cy in self._bresenham(sx, sy, ex, ey):
                    if cx == ex and cy == ey:
                        break
                    i = self._idx(cx, cy)
                    if i is None:
                        continue
                    if self.logodds[i] > 2.5:
                        continue
                    self.logodds[i] = max(-5.0, self.logodds[i] - 0.18)
                # Hit + soft blob so thin chair legs become visible cells
                for dy in range(-HIT_BLOB, HIT_BLOB + 1):
                    for dx in range(-HIT_BLOB, HIT_BLOB + 1):
                        if abs(dx) + abs(dy) > HIT_BLOB:
                            continue
                        tx, ty = ex + dx, ey + dy
                        i = self._idx(tx, ty)
                        if i is None:
                            continue
                        boost = 1.15 if (dx == 0 and dy == 0) else 0.55
                        if self.logodds[i] < 4.0:
                            self.logodds[i] = min(6.0, self.logodds[i] + boost)
                        touched.append((tx, ty))
            self.dirty = True
            if len(touched) >= 8:
                self._polish_edges_unlocked(touched)

    def _polish_edges_unlocked(self, seeds: list[tuple[int, int]]) -> None:
        """Fill 1-cell gaps in furniture blobs (pouf) without deleting thin legs."""
        seen: set[tuple[int, int]] = set()
        for sx, sy in seeds:
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    ix, iy = sx + dx, sy + dy
                    if (ix, iy) in seen:
                        continue
                    seen.add((ix, iy))
                    i = self._idx(ix, iy)
                    if i is None:
                        continue
                    if self.logodds[i] > OCC_DISPLAY:
                        continue
                    neigh = 0
                    for oy in range(-1, 2):
                        for ox in range(-1, 2):
                            if ox == 0 and oy == 0:
                                continue
                            j = self._idx(ix + ox, iy + oy)
                            if j is not None and self.logodds[j] > OCC_SOLID:
                                neigh += 1
                    # Gap inside solid object (pouf) — fill for cleaner border
                    if neigh >= 5:
                        self.logodds[i] = max(self.logodds[i], 1.4)

    def occupied_xy(self, max_points: int = 450) -> np.ndarray:
        with self.lock:
            pts: list[list[float]] = []
            for i, v in enumerate(self.logodds):
                if v <= OCC_DISPLAY:
                    continue
                iy = i // self.w
                ix = i % self.w
                pts.append(
                    [
                        self.origin_x + (ix + 0.5) * self.res,
                        self.origin_y + (iy + 0.5) * self.res,
                    ]
                )
        if not pts:
            return np.zeros((0, 2), dtype=np.float64)
        if len(pts) > max_points:
            step = max(1, len(pts) // max_points)
            pts = pts[::step][:max_points]
        return np.asarray(pts, dtype=np.float64)

    def score_world_hits(self, world: np.ndarray) -> float:
        """Fast scan-to-map score on occupancy grid (O(n))."""
        if world.shape[0] == 0:
            return 0.0
        good = 0
        total = 0
        with self.lock:
            for wx, wy in world:
                ix = int((wx - self.origin_x) / self.res)
                iy = int((wy - self.origin_y) / self.res)
                if not (0 <= ix < self.w and 0 <= iy < self.h):
                    continue
                total += 1
                v = self.logodds[iy * self.w + ix]
                if v > OCC_DISPLAY:
                    good += 1
        if total == 0:
            return 0.0
        return max(0.0, float(good) / float(total))

    @staticmethod
    def _bresenham(x0: int, y0: int, x1: int, y1: int):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            yield x, y
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def to_dict(self, temp_cells: list[list[int]] | None = None) -> dict[str, Any]:
        with self.lock:
            cells: list[list[int]] = []
            occupied = 0
            for i, v in enumerate(self.logodds):
                if v > OCC_SOLID:
                    val = 100
                    occupied += 1
                elif v > OCC_DISPLAY:
                    val = 90  # weak / thin-leg cells
                    occupied += 1
                elif v < -0.7:
                    val = 0
                else:
                    continue
                iy = i // self.w
                ix = i % self.w
                cells.append([ix, iy, val])
            if temp_cells:
                cells.extend(temp_cells)
            return {
                "width": self.w,
                "height": self.h,
                "resolution": self.res,
                "origin": [self.origin_x, self.origin_y],
                "cells": cells,
                "hits": occupied,
            }

    def is_static_occupied(self, ix: int, iy: int, margin: int = 1) -> bool:
        with self.lock:
            for dy in range(-margin, margin + 1):
                for dx in range(-margin, margin + 1):
                    i = self._idx(ix + dx, iy + dy)
                    if i is not None and self.logodds[i] > OCC_DISPLAY:
                        return True
        return False

    def cell_to_world(self, ix: int, iy: int) -> tuple[float, float]:
        return (
            self.origin_x + (ix + 0.5) * self.res,
            self.origin_y + (iy + 0.5) * self.res,
        )

    def save(self, path: Path) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            # Sparse save — fine grids are huge if stored dense
            sparse: list[list[float]] = []
            for i, v in enumerate(self.logodds):
                if abs(v) >= 0.35:
                    sparse.append([i, round(v, 3)])
            payload = {
                "res": self.res,
                "w": self.w,
                "h": self.h,
                "origin_x": self.origin_x,
                "origin_y": self.origin_y,
                "sparse": sparse,
                "saved_at": time.time(),
                "format": "sparse_v1",
            }
            hits = sum(1 for v in self.logodds if v > OCC_SOLID)
            dirty = self.dirty
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
        with self.lock:
            self.dirty = False
            self.last_save = time.time()
        FILE_LOG.info("map saved hits=%s cells_sparse=%s → %s", hits, len(sparse), path)
        return {"ok": True, "path": str(path), "hits": hits, "was_dirty": dirty}

    def load(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if (
            int(payload.get("w", 0)) != self.w
            or int(payload.get("h", 0)) != self.h
            or abs(float(payload.get("res", 0)) - self.res) > 1e-6
        ):
            FILE_LOG.warning(
                "Old map grid mismatch (need res=%.3f %dx%d) — starting empty map",
                self.res,
                self.w,
                self.h,
            )
            return False
        with self.lock:
            self.origin_x = float(payload.get("origin_x", self.origin_x))
            self.origin_y = float(payload.get("origin_y", self.origin_y))
            self.logodds = [0.0] * (self.w * self.h)
            sparse = payload.get("sparse")
            odds = payload.get("logodds")
            if isinstance(sparse, list):
                for item in sparse:
                    if not isinstance(item, (list, tuple)) or len(item) < 2:
                        continue
                    i = int(item[0])
                    if 0 <= i < len(self.logodds):
                        self.logodds[i] = float(item[1])
            elif isinstance(odds, list) and len(odds) == self.w * self.h:
                self.logodds = [float(v) for v in odds]
            else:
                return False
            self.dirty = False
            self.last_save = float(payload.get("saved_at", time.time()))
        FILE_LOG.info("map loaded from %s", path)
        return True


def _astar(
    blocked: set[tuple[int, int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    w: int,
    h: int,
) -> list[tuple[int, int]] | None:
    if start == goal:
        return [start]
    if start in blocked or goal in blocked:
        # allow goal if only soft-blocked; still try nearest free
        pass

    def inb(p: tuple[int, int]) -> bool:
        return 0 <= p[0] < w and 0 <= p[1] < h

    def heur(a: tuple[int, int], b: tuple[int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_h: list[tuple[float, int, tuple[int, int]]] = []
    heapq.heappush(open_h, (heur(start, goal), 0, start))
    came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    gscore = {start: 0}
    closed: set[tuple[int, int]] = set()
    dirs = (
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    )
    while open_h:
        _, _, cur = heapq.heappop(open_h)
        if cur in closed:
            continue
        if cur == goal:
            path = [cur]
            while came[cur] is not None:
                cur = came[cur]  # type: ignore[assignment]
                path.append(cur)
            path.reverse()
            return path
        closed.add(cur)
        for dx, dy in dirs:
            nxt = (cur[0] + dx, cur[1] + dy)
            if not inb(nxt) or nxt in blocked or nxt in closed:
                continue
            step = 1.414 if dx and dy else 1.0
            ng = gscore[cur] + step
            if ng < gscore.get(nxt, 1e18):
                gscore[nxt] = ng
                came[nxt] = cur
                heapq.heappush(open_h, (ng + heur(nxt, goal), id(nxt), nxt))
    return None


class ScanBridge(Node):
    def __init__(self) -> None:
        super().__init__("lidar_map_bridge")
        self._lock = threading.Lock()
        self._points: list[dict[str, float]] = []
        self._stamp = 0.0
        self._ok = False
        self._error = "ожидание /scan"
        self._pose = {"x": 0.0, "y": 0.0, "yaw": 0.0, "ok": False}
        self._odom = {"x": 0.0, "y": 0.0, "yaw": 0.0}
        self._odom_stamp = 0.0
        self._odom_ok = False
        self._prev_world: np.ndarray | None = None
        self._last_score = 0.0
        self._mapping_ok = True
        self._cmd_vx = 0.0
        self._cmd_vy = 0.0
        self._cmd_w = 0.0
        self._cmd_stamp = 0.0
        self._map_frozen = False
        self._temp: dict[int, float] = {}  # cell index → last-seen time
        self._nav_path: list[tuple[float, float]] = []
        self._nav_goal: tuple[float, float] | None = None
        self._nav_i = 0
        self._teleop_stamp = 0.0
        self._last_scan_t = 0.0
        self._map_bootstrap_scans = 120  # free painting after clear / start
        self.omap = OccupancyMap()
        self._scan_count = 0
        loaded = self.omap.load(MAP_PATH)
        if loaded:
            self.get_logger().info(f"Загружена память карты: {MAP_PATH}")
            FILE_LOG.info("boot: loaded map %s", MAP_PATH)
        else:
            self.get_logger().info("Новая карта (памяти на диске нет / другой grid)")
            FILE_LOG.info(
                "boot: empty map res=%.3f robot=%.2fx%.2f r=%.2f nav_r_cells=%s log=%s",
                MAP_RES,
                ROBOT_LENGTH_M,
                ROBOT_WIDTH_M,
                ROBOT_RADIUS_M,
                NAV_ROBOT_R,
                LOG_PATH,
            )
        self.get_logger().info(
            f"DRIVE map: robot {ROBOT_LENGTH_M:.2f}x{ROBOT_WIDTH_M:.2f}m "
            f"r={ROBOT_RADIUS_M:.2f}m grid={MAP_RES}m"
        )
        self._cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(LaserScan, "/scan", self._on_scan, SCAN_QOS)
        self.create_subscription(Odometry, "/odom", self._on_odom, ODOM_QOS)
        self.create_timer(AUTOSAVE_SEC, self._autosave)
        self.create_timer(0.05, self._cmd_watchdog)
        self.create_timer(0.10, self._nav_tick)

    def _autosave(self) -> None:
        with self.omap.lock:
            dirty = self.omap.dirty
        if dirty:
            info = self.omap.save(MAP_PATH)
            self.get_logger().info(
                f"Автосохранение: {info.get('hits')} стен → {MAP_PATH}"
            )
            FILE_LOG.info("autosave hits=%s", info.get("hits"))

    def _publish_twist(self, vx: float, vy: float, w: float) -> None:
        msg = Twist()
        msg.linear.x = float(vx)
        msg.linear.y = float(vy)
        msg.linear.z = 0.0
        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = float(w)
        self._cmd_pub.publish(msg)

    def set_cmd(self, vx: float, vy: float, w: float) -> dict[str, Any]:
        vx = _clamp(float(vx), -CMD_VX_MAX, CMD_VX_MAX)
        vy = _clamp(float(vy), -CMD_VY_MAX, CMD_VY_MAX)
        w = _clamp(float(w), -CMD_W_MAX, CMD_W_MAX)
        with self._lock:
            self._cmd_vx = vx
            self._cmd_vy = vy
            self._cmd_w = w
            self._cmd_stamp = time.time()
            if abs(vx) > 0.02 or abs(vy) > 0.02 or abs(w) > 0.05:
                self._teleop_stamp = time.time()
                self._nav_path = []
                self._nav_goal = None
                self._nav_i = 0
        self._write_cmd_file(vx, vy, w)
        self._publish_twist(vx, vy, w)
        return {"ok": True, "vx": vx, "vy": vy, "w": w}

    def stop_cmd(self) -> dict[str, Any]:
        with self._lock:
            self._cmd_vx = 0.0
            self._cmd_vy = 0.0
            self._cmd_w = 0.0
            self._cmd_stamp = time.time()
            self._nav_path = []
            self._nav_goal = None
            self._nav_i = 0
        self._write_cmd_file(0.0, 0.0, 0.0)
        self._publish_twist(0.0, 0.0, 0.0)
        return {"ok": True, "vx": 0.0, "vy": 0.0, "w": 0.0}

    def _write_cmd_file(self, vx: float, vy: float, w: float) -> None:
        try:
            CMD_FILE.write_text(
                json.dumps({"vx": vx, "vy": vy, "w": w, "t": time.time()}),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _cmd_watchdog(self) -> None:
        """20 Hz: файл для Arduino-драйвера + /cmd_vel."""
        with self._lock:
            age = time.time() - self._cmd_stamp if self._cmd_stamp > 0 else 1e9
            if age > CMD_WATCHDOG_SEC:
                self._cmd_vx = 0.0
                self._cmd_vy = 0.0
                self._cmd_w = 0.0
            vx = self._cmd_vx
            vy = self._cmd_vy
            w = self._cmd_w
        self._write_cmd_file(vx, vy, w)
        self._publish_twist(vx, vy, w)

    def _on_odom(self, msg: Odometry) -> None:
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = _yaw_from_quat(q.x, q.y, q.z, q.w)
        with self._lock:
            self._odom = {"x": float(p.x), "y": float(p.y), "yaw": float(yaw)}
            self._odom_stamp = time.time()
            self._odom_ok = True

    def _local_from_scan(
        self, msg: LaserScan
    ) -> tuple[np.ndarray, list[tuple[float, float]]]:
        angle = float(msg.angle_min)
        rmin = max(float(msg.range_min), MIN_RANGE_SHOW)
        rmax = min(float(msg.range_max), MAX_RANGE)
        locals_xy: list[list[float]] = []
        map_hits_local: list[tuple[float, float]] = []
        for i, r in enumerate(msg.ranges):
            dist = float(r)
            if math.isfinite(dist) and rmin <= dist <= rmax:
                lx = dist * math.cos(angle)
                ly = dist * math.sin(angle)
                if i % ICP_STRIDE == 0:
                    locals_xy.append([lx, ly])
                # Every beam for mapping — thin chair legs otherwise vanish
                if dist >= MIN_RANGE_MAP and (i % MAP_HIT_STRIDE == 0):
                    map_hits_local.append((lx, ly))
            angle += float(msg.angle_increment)
        if len(locals_xy) > ICP_MAX_POINTS:
            step = max(1, len(locals_xy) // ICP_MAX_POINTS)
            locals_xy = locals_xy[::step][:ICP_MAX_POINTS]
        return np.asarray(locals_xy, dtype=np.float64), map_hits_local

    def _odom_fresh(self) -> bool:
        with self._lock:
            if not self._odom_ok:
                return False
            return (time.time() - self._odom_stamp) <= ODOM_STALE_SEC

    def _on_scan(self, msg: LaserScan) -> None:
        local, map_hits_local = self._local_from_scan(msg)
        odom_ok = self._odom_fresh()
        with self._lock:
            if odom_ok:
                ox = float(self._odom["x"])
                oy = float(self._odom["y"])
                oyaw = float(self._odom["yaw"])
            else:
                ox = float(self._pose["x"])
                oy = float(self._pose["y"])
                oyaw = float(self._pose["yaw"])
            # Last map pose is more stable than spinning encoder odom.
            lx = float(self._pose["x"])
            ly = float(self._pose["y"])
            lyaw = float(self._pose["yaw"])
            pose_ok = bool(self._pose.get("ok"))
            cmd_vx = float(self._cmd_vx)
            cmd_vy = float(self._cmd_vy)
            cmd_w = float(self._cmd_w)
            prev = None if self._prev_world is None else self._prev_world.copy()
            last_t = float(self._last_scan_t)

        now = time.time()
        dt = 0.1 if last_t <= 0 else _clamp(now - last_t, 0.02, 0.35)

        # Motion prior from teleop cmd (avoids encoder yaw spin)
        c0, s0 = math.cos(lyaw), math.sin(lyaw)
        pred_x = lx + (c0 * cmd_vx - s0 * cmd_vy) * dt
        pred_y = ly + (s0 * cmd_vx + c0 * cmd_vy) * dt
        pred_yaw = _wrap_angle(lyaw + cmd_w * dt)
        if pose_ok:
            x, y, yaw = pred_x, pred_y, pred_yaw
        elif odom_ok:
            x, y, yaw = ox, oy, oyaw
        else:
            x, y, yaw = lx, ly, lyaw

        score = 0.0
        mapping_ok = False
        map_pts = self.omap.occupied_xy()
        with self._lock:
            bootstrap = self._map_bootstrap_scans > 0
            if bootstrap:
                self._map_bootstrap_scans -= 1

        # Young map / just cleared: always allow wall painting (strict CSM comes later)
        young = bootstrap or map_pts.shape[0] < 120

        if local.shape[0] >= 25:
            ref_parts: list[np.ndarray] = []
            if map_pts.shape[0] >= 40:
                ref_parts.append(map_pts)
            if prev is not None and prev.shape[0] >= 25:
                ref_parts.append(prev)

            if ref_parts:
                ref = np.vstack(ref_parts)
                score_fn = (
                    self.omap.score_world_hits if map_pts.shape[0] >= 40 else None
                )
                if map_pts.shape[0] >= 40 and not young:
                    nx, ny, nyaw, score = _correlative_search(
                        local,
                        ref,
                        x,
                        y,
                        yaw,
                        score_fn=score_fn,
                        yaw_span=math.radians(40.0),
                        yaw_step=math.radians(3.0),
                        xy_span=0.40,
                        xy_step=0.10,
                    )
                    if score >= 0.26:
                        x, y, yaw = nx, ny, nyaw
                        mapping_ok = True
                    elif score >= 0.16:
                        # Weak but usable — update pose lightly, still paint
                        x, y, yaw = nx, ny, nyaw
                        mapping_ok = True
                    else:
                        mapping_ok = False
                else:
                    # Bootstrap / young map: refine if possible, always paint
                    nx, ny, nyaw, score = _correlative_search(
                        local,
                        ref,
                        x,
                        y,
                        yaw,
                        score_fn=score_fn,
                        yaw_span=CSM_REFINE_YAW_SPAN,
                        yaw_step=CSM_REFINE_YAW_STEP,
                        xy_span=CSM_REFINE_XY_SPAN,
                        xy_step=CSM_REFINE_XY_STEP,
                    )
                    if score >= 0.18:
                        x, y, yaw = nx, ny, nyaw
                    mapping_ok = True
            else:
                mapping_ok = True
                score = 1.0
        else:
            mapping_ok = young or map_pts.shape[0] < 20
            score = 0.0

        world = (
            _transform_local(local, x, y, yaw)
            if local.shape[0]
            else np.zeros((0, 2))
        )
        c, s = math.cos(yaw), math.sin(yaw)
        points: list[dict[str, float]] = []
        hits: list[tuple[float, float]] = []
        for hlx, hly in map_hits_local:
            wx = x + c * hlx - s * hly
            wy = y + s * hlx + c * hly
            hits.append((wx, wy))
            points.append({"x": wx, "y": wy, "r": math.hypot(hlx, hly)})
        if not points and world.shape[0]:
            for wx, wy in world:
                points.append({"x": float(wx), "y": float(wy), "r": 0.0})

        with self._lock:
            frozen = self._map_frozen

        # Paint walls only with trusted pose — stops redrawing the same wall in an arc
        if hits and mapping_ok:
            if frozen:
                self._update_temp_from_hits(hits)
            else:
                self.omap.integrate(x, y, hits)

        with self._lock:
            self._pose = {"x": x, "y": y, "yaw": yaw, "ok": True}
            self._prev_world = world if world.shape[0] else self._prev_world
            self._points = points
            self._stamp = time.time()
            self._last_scan_t = now
            self._ok = True
            self._error = ""
            self._last_score = float(score)
            self._mapping_ok = bool(mapping_ok)
            self._odom_ok = odom_ok
            self._scan_count += 1
            sc = self._scan_count
        if sc % 50 == 0:
            hits_n = 0
            with self.omap.lock:
                hits_n = sum(1 for v in self.omap.logodds if v > OCC_DISPLAY)
            FILE_LOG.info(
                "scan#%s mapping=%s score=%.2f map_hits=%s frozen=%s pose=(%.2f,%.2f,%.2f)",
                sc,
                mapping_ok,
                score,
                hits_n,
                frozen,
                x,
                y,
                yaw,
            )

    def _update_temp_from_hits(self, hits: list[tuple[float, float]]) -> None:
        now = time.time()
        fresh: list[int] = []
        for hx, hy in hits:
            ix, iy = self.omap._world_to_cell(hx, hy)
            if self.omap.is_static_occupied(ix, iy, margin=1):
                continue
            i = self.omap._idx(ix, iy)
            if i is None:
                continue
            fresh.append(i)
            for dy in range(-TEMP_INFLATE, TEMP_INFLATE + 1):
                for dx in range(-TEMP_INFLATE, TEMP_INFLATE + 1):
                    if dx * dx + dy * dy > TEMP_INFLATE * TEMP_INFLATE:
                        continue
                    nx, ny = ix + dx, iy + dy
                    if self.omap.is_static_occupied(nx, ny, margin=0):
                        continue
                    j = self.omap._idx(nx, ny)
                    if j is not None:
                        fresh.append(j)
        with self._lock:
            self._temp = {
                i: t for i, t in self._temp.items() if now - t <= TEMP_TTL_SEC
            }
            for i in fresh:
                self._temp[i] = now

    def _temp_cells_for_ui(self) -> list[list[int]]:
        now = time.time()
        out: list[list[int]] = []
        with self._lock:
            live = {i: t for i, t in self._temp.items() if now - t <= TEMP_TTL_SEC}
            self._temp = live
            items = list(live.keys())
        for i in items:
            iy = i // self.omap.w
            ix = i % self.omap.w
            out.append([ix, iy, TEMP_CELL_VAL])
        return out

    def set_frozen(self, frozen: bool) -> dict[str, Any]:
        with self._lock:
            self._map_frozen = bool(frozen)
            if not self._map_frozen:
                self._temp.clear()
            self._nav_path = []
            self._nav_goal = None
            self._nav_i = 0
            was = self._map_frozen
        if was:
            info = self.omap.save(MAP_PATH)
            self.get_logger().info(
                f"Карта заморожена, сохранено стен={info.get('hits')}"
            )
            FILE_LOG.info("freeze ON hits=%s", info.get("hits"))
        else:
            FILE_LOG.info("freeze OFF — wall writing enabled")
        return {"ok": True, "frozen": was, "hits": self.omap.to_dict().get("hits", 0)}

    def _build_blocked(self) -> set[tuple[int, int]]:
        now = time.time()
        with self._lock:
            temp_idx = [
                i for i, t in self._temp.items() if now - t <= TEMP_TTL_SEC
            ]
        blocked: set[tuple[int, int]] = set()
        with self.omap.lock:
            for i, v in enumerate(self.omap.logodds):
                if v <= OCC_SOLID:
                    continue
                iy = i // self.omap.w
                ix = i % self.omap.w
                for dy in range(-NAV_ROBOT_R, NAV_ROBOT_R + 1):
                    for dx in range(-NAV_ROBOT_R, NAV_ROBOT_R + 1):
                        if dx * dx + dy * dy > NAV_ROBOT_R * NAV_ROBOT_R:
                            continue
                        blocked.add((ix + dx, iy + dy))
        for i in temp_idx:
            iy = i // self.omap.w
            ix = i % self.omap.w
            for dy in range(-NAV_ROBOT_R, NAV_ROBOT_R + 1):
                for dx in range(-NAV_ROBOT_R, NAV_ROBOT_R + 1):
                    if dx * dx + dy * dy > NAV_ROBOT_R * NAV_ROBOT_R:
                        continue
                    blocked.add((ix + dx, iy + dy))
        return blocked

    def set_goal(self, gx: float, gy: float) -> dict[str, Any]:
        with self._lock:
            if not self._map_frozen:
                return {"ok": False, "error": "сначала заморозь комнату"}
            x = float(self._pose["x"])
            y = float(self._pose["y"])
        sx, sy = self.omap._world_to_cell(x, y)
        ex, ey = self.omap._world_to_cell(gx, gy)
        blocked = self._build_blocked()
        # If start/goal blocked, search nearby free cell
        def nearest_free(ix: int, iy: int) -> tuple[int, int] | None:
            for rad in range(0, 12):
                for dy in range(-rad, rad + 1):
                    for dx in range(-rad, rad + 1):
                        p = (ix + dx, iy + dy)
                        if (
                            0 <= p[0] < self.omap.w
                            and 0 <= p[1] < self.omap.h
                            and p not in blocked
                        ):
                            return p
            return None

        start = nearest_free(sx, sy)
        goal = nearest_free(ex, ey)
        if start is None or goal is None:
            return {"ok": False, "error": "старт/цель в препятствии"}
        path_cells = _astar(blocked, start, goal, self.omap.w, self.omap.h)
        if not path_cells:
            return {"ok": False, "error": "путь не найден"}
        # downsample waypoints
        world_path = [self.omap.cell_to_world(ix, iy) for ix, iy in path_cells]
        sparse: list[tuple[float, float]] = []
        for p in world_path:
            if not sparse or math.hypot(p[0] - sparse[-1][0], p[1] - sparse[-1][1]) >= 0.25:
                sparse.append(p)
        if sparse[-1] != world_path[-1]:
            sparse.append(world_path[-1])
        with self._lock:
            self._nav_path = sparse
            self._nav_goal = (float(gx), float(gy))
            self._nav_i = 0
        FILE_LOG.info(
            "goal set (%.2f,%.2f) path_len=%s blocked≈nav_r=%s",
            gx,
            gy,
            len(sparse),
            NAV_ROBOT_R,
        )
        return {"ok": True, "path_len": len(sparse), "goal": [gx, gy]}

    def _nav_tick(self) -> None:
        with self._lock:
            if time.time() - self._teleop_stamp < 0.35:
                return
            path = list(self._nav_path)
            goal = self._nav_goal
            i = self._nav_i
            x = float(self._pose["x"])
            y = float(self._pose["y"])
            yaw = float(self._pose["yaw"])
            frozen = self._map_frozen
        if not frozen or not path or goal is None:
            return
        # replan lightly if people moved onto path (every ~1s via scan updates —
        # check remaining waypoints against blocked)
        blocked = self._build_blocked()
        while i < len(path):
            ix, iy = self.omap._world_to_cell(path[i][0], path[i][1])
            if (ix, iy) in blocked and i + 1 < len(path):
                i += 1
                continue
            break
        if i >= len(path):
            # try replan to goal
            self.set_goal(goal[0], goal[1])
            return
        tx, ty = path[i]
        dist = math.hypot(tx - x, ty - y)
        if dist < 0.22 and i + 1 < len(path):
            i += 1
            tx, ty = path[i]
            dist = math.hypot(tx - x, ty - y)
        with self._lock:
            self._nav_i = i
        if math.hypot(goal[0] - x, goal[1] - y) < NAV_GOAL_TOL:
            with self._lock:
                self._nav_path = []
                self._nav_goal = None
                self._nav_i = 0
            self._write_cmd_file(0.0, 0.0, 0.0)
            self._publish_twist(0.0, 0.0, 0.0)
            return
        want = math.atan2(ty - y, tx - x)
        err = _wrap_angle(want - yaw)
        w = _clamp(1.8 * err, -NAV_W_MAX, NAV_W_MAX)
        vx = NAV_VX if abs(err) < 0.7 else NAV_VX * 0.25
        with self._lock:
            self._cmd_vx = vx
            self._cmd_vy = 0.0
            self._cmd_w = w
            self._cmd_stamp = time.time()
        self._write_cmd_file(vx, 0.0, w)
        self._publish_twist(vx, 0.0, w)

    def snapshot(self) -> dict[str, Any]:
        temp_cells = self._temp_cells_for_ui()
        with self._lock:
            odom_ok = bool(
                self._odom_ok
                and (time.time() - self._odom_stamp) <= ODOM_STALE_SEC
            )
            frozen = self._map_frozen
            path = [[p[0], p[1]] for p in self._nav_path]
            goal = list(self._nav_goal) if self._nav_goal else None
            if not self._ok:
                return {
                    "ok": False,
                    "error": self._error,
                    "points": [],
                    "pose": dict(self._pose),
                    "mode": "drive",
                    "odom_ok": odom_ok,
                    "frozen": frozen,
                    "temp_hits": len(temp_cells),
                    "map": self.omap.to_dict(temp_cells),
                    "path": path,
                    "goal": goal,
                    "robot": {
                        "length": ROBOT_LENGTH_M,
                        "width": ROBOT_WIDTH_M,
                        "radius": ROBOT_RADIUS_M,
                    },
                }
            age = time.time() - self._stamp
            saved_ago = None
            if self.omap.last_save > 0:
                saved_ago = int(time.time() - self.omap.last_save)
            base = {
                "ok": True,
                "mode": "drive",
                "points": list(self._points),
                "pose": dict(self._pose),
                "map": self.omap.to_dict(temp_cells),
                "odom_ok": odom_ok,
                "saved_ago": saved_ago,
                "score": self._last_score,
                "mapping": self._mapping_ok,
                "frozen": frozen,
                "temp_hits": len(temp_cells),
                "path": path,
                "goal": goal,
                "robot": {
                    "length": ROBOT_LENGTH_M,
                    "width": ROBOT_WIDTH_M,
                    "radius": ROBOT_RADIUS_M,
                },
            }
            if age > 2.0:
                base["stale"] = True
                base["error"] = "лидар молчит — проверь USB / перезапуск драйвера"
            else:
                base["stale"] = False
            return base

    def clear_map(self) -> dict[str, Any]:
        with self._lock:
            if self._odom_ok and (time.time() - self._odom_stamp) <= ODOM_STALE_SEC:
                x = float(self._odom["x"])
                y = float(self._odom["y"])
                yaw = float(self._odom["yaw"])
            else:
                x = float(self._pose["x"])
                y = float(self._pose["y"])
                yaw = float(self._pose["yaw"])
            self._pose = {"x": x, "y": y, "yaw": yaw, "ok": True}
            self._prev_world = None
            self._last_score = 0.0
            self._mapping_ok = True
            self._map_frozen = False
            self._temp.clear()
            self._nav_path = []
            self._nav_goal = None
            self._nav_i = 0
            self._map_bootstrap_scans = 120
            self._last_scan_t = 0.0
        self.omap.recentre(x, y)
        self.omap.save(MAP_PATH)
        self.get_logger().info("Карта сброшена — запись стен снова включена")
        FILE_LOG.info("map cleared at pose=(%.2f,%.2f,%.2f) bootstrap=120", x, y, yaw)
        return {"ok": True, "frozen": False, "message": "карта сброшена — едь, стены копятся"}

    def save_map(self) -> dict[str, Any]:
        return self.omap.save(MAP_PATH)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _send_json(handler: BaseHTTPRequestHandler, payload: dict[str, Any], code: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(bridge: ScanBridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                body = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path.startswith("/api/scan"):
                _send_json(self, bridge.snapshot())
                return
            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path.startswith("/api/cmd/stop"):
                _send_json(self, bridge.stop_cmd())
                return
            if path.startswith("/api/cmd"):
                data = _read_json_body(self)
                try:
                    vx = float(data.get("vx", 0.0))
                    vy = float(data.get("vy", 0.0))
                    w = float(data.get("w", 0.0))
                except (TypeError, ValueError):
                    _send_json(self, {"ok": False, "error": "bad cmd"}, 400)
                    return
                _send_json(self, bridge.set_cmd(vx, vy, w))
                return
            if path.startswith("/api/clear"):
                _send_json(self, bridge.clear_map())
                return
            if path.startswith("/api/save"):
                _send_json(self, bridge.save_map())
                return
            if path.startswith("/api/freeze"):
                data = _read_json_body(self)
                frozen = bool(data.get("frozen", True))
                _send_json(self, bridge.set_frozen(frozen))
                return
            if path.startswith("/api/goal"):
                data = _read_json_body(self)
                try:
                    gx = float(data.get("x", 0.0))
                    gy = float(data.get("y", 0.0))
                except (TypeError, ValueError):
                    _send_json(self, {"ok": False, "error": "bad goal"}, 400)
                    return
                _send_json(self, bridge.set_goal(gx, gy))
                return
            self.send_error(404)

    return Handler


def main() -> None:
    rclpy.init()
    bridge = ScanBridge()
    httpd = ThreadingHTTPServer((HOST, PORT), make_handler(bridge))

    def spin() -> None:
        while rclpy.ok():
            rclpy.spin_once(bridge, timeout_sec=0.05)

    threading.Thread(target=spin, daemon=True).start()
    print(f"http://0.0.0.0:{PORT}/  (drive mode + web teleop)", flush=True)
    print(f"map memory: {MAP_PATH}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            bridge.stop_cmd()
        except Exception:
            pass
        try:
            bridge.save_map()
        except OSError:
            pass
        httpd.server_close()
        bridge.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
