#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS Unified Client - Единое приложение для всех функций
Современный интерфейс в стиле 2099 с интеграцией всех модулей
"""

import http.server
import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

# Добавляем текущую директорию в путь
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# Импорты модулей
try:
    import requests
    from nexus_client import (
        load_token, check_access, make_http_session,
        resolve_app_url, request_device_code, poll_for_token,
        save_token, launch_payload, log
    )
    HAS_CLIENT = True
except ImportError:
    HAS_CLIENT = False
    log = print

try:
    import launcher
    HAS_LAUNCHER = True
except ImportError:
    HAS_LAUNCHER = False

# Конфигурация
PORT = int(os.environ.get("NEXUS_PORT", "7777"))
UI_WIDTH = 1200
UI_HEIGHT = 800

# Глобальное состояние
_STATE = {
    "subscription": {
        "has_access": False,
        "email": None,
        "ends_at": None,
        "checked_at": None,
    },
    "launcher": {
        "running": False,
        "progress": 0,
        "status": "Готов",
    },
}
_STATE_LOCK = threading.Lock()


def update_subscription_status():
    """Обновить статус подписки"""
    if not HAS_CLIENT:
        return

    try:
        token = load_token()
        if not token:
            return

        sess = make_http_session()
        has_access, ends_at, http_st, _, email = check_access(sess, token)

        if http_st == 200:
            with _STATE_LOCK:
                _STATE["subscription"] = {
                    "has_access": bool(has_access),
                    "email": email,
                    "ends_at": ends_at,
                    "checked_at": datetime.now().isoformat(),
                }
    except Exception as e:
        log(f"update_subscription_status error: {e}")


def format_date(iso_date):
    """Форматировать дату"""
    if not iso_date:
        return "—"
    try:
        s = str(iso_date).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(iso_date)


# HTML интерфейс
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXUS 2099</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{
  background:#000;
  color:#0ff;
  font-family:'Orbitron',monospace;
  position:relative;
}
canvas#particles{
  position:fixed;
  inset:0;
  z-index:0;
}
.vignette{
  position:fixed;
  inset:0;
  z-index:1;
  pointer-events:none;
  background:radial-gradient(ellipse at center,transparent 0%,rgba(0,0,0,.9) 100%);
}
.scanline{
  position:fixed;
  inset:0;
  z-index:2;
  pointer-events:none;
  background:linear-gradient(rgba(0,255,255,.03) 50%,transparent 50%);
  background-size:100% 4px;
  animation:scan 8s linear infinite;
}
@keyframes scan{from{background-position:0 0}to{background-position:0 100%}}
.app{
  position:relative;
  z-index:10;
  min-height:100vh;
  display:flex;
  flex-direction:column;
  padding:20px;
}
.header{
  text-align:center;
  margin-bottom:30px;
}
.logo{
  font-size:clamp(32px,8vw,64px);
  font-weight:900;
  letter-spacing:.3em;
  text-shadow:0 0 20px #0ff,0 0 40px #0ff,0 0 60px #0ff;
  animation:glow 2s ease-in-out infinite alternate;
}
@keyframes glow{
  from{text-shadow:0 0 20px #0ff,0 0 40px #0ff,0 0 60px #0ff}
  to{text-shadow:0 0 30px #0ff,0 0 60px #0ff,0 0 90px #0ff}
}
.subtitle{
  font-size:14px;
  letter-spacing:.4em;
  color:#0ff;
  opacity:.6;
  margin-top:10px;
}
.container{
  flex:1;
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
  gap:20px;
  max-width:1400px;
  margin:0 auto;
  width:100%;
}
.card{
  background:rgba(0,20,20,.6);
  border:2px solid rgba(0,255,255,.3);
  padding:24px;
  backdrop-filter:blur(10px);
  position:relative;
  overflow:hidden;
  transition:all .3s;
}
.card::before{
  content:'';
  position:absolute;
  top:-50%;
  left:-50%;
  width:200%;
  height:200%;
  background:radial-gradient(circle,rgba(0,255,255,.1),transparent 70%);
  opacity:0;
  transition:opacity .3s;
}
.card:hover{
  border-color:#0ff;
  box-shadow:0 0 30px rgba(0,255,255,.3);
  transform:translateY(-5px);
}
.card:hover::before{
  opacity:1;
  animation:rotate 3s linear infinite;
}
@keyframes rotate{
  from{transform:rotate(0deg)}
  to{transform:rotate(360deg)}
}
.card-title{
  font-size:18px;
  font-weight:700;
  margin-bottom:16px;
  text-transform:uppercase;
  letter-spacing:.2em;
  position:relative;
  z-index:1;
}
.card-content{
  position:relative;
  z-index:1;
}
.status-row{
  display:flex;
  justify-content:space-between;
  margin:12px 0;
  font-size:13px;
}
.status-label{
  color:rgba(0,255,255,.6);
  text-transform:uppercase;
  letter-spacing:.1em;
}
.status-value{
  color:#0ff;
  font-weight:500;
}
.status-active{
  color:#0f0;
  text-shadow:0 0 10px #0f0;
}
.status-inactive{
  color:#f00;
  text-shadow:0 0 10px #f00;
}
.btn{
  width:100%;
  padding:14px 24px;
  margin-top:12px;
  background:rgba(0,255,255,.1);
  border:2px solid #0ff;
  color:#0ff;
  font-family:'Orbitron',monospace;
  font-size:13px;
  font-weight:700;
  letter-spacing:.15em;
  cursor:pointer;
  transition:all .3s;
  text-transform:uppercase;
  position:relative;
  overflow:hidden;
}
.btn::before{
  content:'';
  position:absolute;
  top:50%;
  left:50%;
  width:0;
  height:0;
  background:#0ff;
  transform:translate(-50%,-50%);
  transition:all .4s;
  border-radius:50%;
}
.btn:hover{
  background:#0ff;
  color:#000;
  box-shadow:0 0 20px #0ff;
  transform:scale(1.02);
}
.btn:hover::before{
  width:300%;
  height:300%;
}
.btn:active{
  transform:scale(.98);
}
.btn:disabled{
  opacity:.3;
  cursor:not-allowed;
  transform:none;
}
.btn-primary{
  background:rgba(0,255,255,.2);
  border-color:#0ff;
  box-shadow:0 0 15px rgba(0,255,255,.2);
}
.progress-bar{
  width:100%;
  height:8px;
  background:rgba(0,255,255,.1);
  border:1px solid rgba(0,255,255,.3);
  margin:16px 0;
  position:relative;
  overflow:hidden;
}
.progress-fill{
  height:100%;
  background:linear-gradient(90deg,#0ff,#0f0);
  width:0%;
  transition:width .3s;
  box-shadow:0 0 10px #0ff;
}
.message{
  margin-top:12px;
  padding:12px;
  background:rgba(0,255,255,.05);
  border-left:3px solid #0ff;
  font-size:12px;
  line-height:1.6;
}
.grid-2{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:12px;
}
@media(max-width:768px){
  .container{grid-template-columns:1fr}
  .grid-2{grid-template-columns:1fr}
}
</style>
</head>
<body>
<canvas id="particles"></canvas>
<div class="vignette"></div>
<div class="scanline"></div>
<div class="app">
  <div class="header">
    <div class="logo">NEXUS</div>
    <div class="subtitle">UNIFIED CLIENT 2099</div>
  </div>

  <div class="container">
    <!-- Subscription Card -->
    <div class="card">
      <div class="card-title">⚡ Подписка</div>
      <div class="card-content">
        <div class="status-row">
          <span class="status-label">Статус</span>
          <span class="status-value" id="sub-status">—</span>
        </div>
        <div class="status-row">
          <span class="status-label">Аккаунт</span>
          <span class="status-value" id="sub-email">—</span>
        </div>
        <div class="status-row">
          <span class="status-label">Действует до</span>
          <span class="status-value" id="sub-ends">—</span>
        </div>
        <button class="btn" id="btn-refresh" onclick="refreshStatus()">Обновить</button>
        <button class="btn" id="btn-account" onclick="openAccount()">Кабинет</button>
      </div>
    </div>

    <!-- Launcher Card -->
    <div class="card">
      <div class="card-title">🚀 Автоматизация</div>
      <div class="card-content">
        <div class="status-row">
          <span class="status-label">Статус</span>
          <span class="status-value" id="launcher-status">Готов</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" id="launcher-progress"></div>
        </div>
        <button class="btn btn-primary" id="btn-launch" onclick="launchAutomation()">Запустить</button>
        <div class="message" id="launcher-msg" style="display:none"></div>
      </div>
    </div>

    <!-- Quick Actions Card -->
    <div class="card">
      <div class="card-title">⚙️ Быстрые действия</div>
      <div class="card-content">
        <div class="grid-2">
          <button class="btn" onclick="openLogs()">Логи</button>
          <button class="btn" onclick="openDocs()">Документация</button>
        </div>
        <button class="btn" onclick="exitApp()">Выход</button>
      </div>
    </div>
  </div>
</div>

<script>
// Particles
const canvas=document.getElementById('particles');
const ctx=canvas.getContext('2d');
let w=canvas.width=innerWidth;
let h=canvas.height=innerHeight;
const particles=[];
for(let i=0;i<80;i++){
  particles.push({
    x:Math.random()*w,
    y:Math.random()*h,
    vx:(Math.random()-.5)*.3,
    vy:(Math.random()-.5)*.3,
    r:Math.random()*2+1
  });
}
function animate(){
  ctx.fillStyle='rgba(0,0,0,.1)';
  ctx.fillRect(0,0,w,h);
  particles.forEach(p=>{
    p.x+=p.vx;
    p.y+=p.vy;
    if(p.x<0||p.x>w)p.vx*=-1;
    if(p.y<0||p.y>h)p.vy*=-1;
    ctx.beginPath();
    ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
    ctx.fillStyle='rgba(0,255,255,.5)';
    ctx.shadowBlur=10;
    ctx.shadowColor='#0ff';
    ctx.fill();
  });
  requestAnimationFrame(animate);
}
animate();
addEventListener('resize',()=>{w=canvas.width=innerWidth;h=canvas.height=innerHeight});

// API
function post(path,cb){
  fetch(path,{method:'POST'})
    .then(r=>r.json())
    .then(cb)
    .catch(e=>console.error(e));
}

function refreshStatus(){
  post('/api/refresh',data=>{
    updateUI(data);
  });
}

function launchAutomation(){
  const btn=document.getElementById('btn-launch');
  btn.disabled=true;
  btn.textContent='Запуск...';
  post('/api/launch',data=>{
    if(data.ok){
      document.getElementById('launcher-msg').style.display='block';
      document.getElementById('launcher-msg').textContent=data.message||'Запущено';
    }else{
      alert(data.error||'Ошибка запуска');
      btn.disabled=false;
      btn.textContent='Запустить';
    }
  });
}

function openAccount(){
  post('/api/account',data=>{
    if(data.url)window.open(data.url,'_blank');
  });
}

function openLogs(){
  post('/api/logs',data=>{
    if(data.path)alert('Логи: '+data.path);
  });
}

function openDocs(){
  window.open('https://github.com/wedenjpin2007ru-cmyk/nexus-web','_blank');
}

function exitApp(){
  if(confirm('Выйти из приложения?')){
    post('/api/exit',()=>{
      window.close();
    });
  }
}

function updateUI(data){
  const sub=data.subscription||{};
  document.getElementById('sub-status').textContent=sub.has_access?'● АКТИВНА':'○ НЕТ ДОСТУПА';
  document.getElementById('sub-status').className='status-value '+(sub.has_access?'status-active':'status-inactive');
  document.getElementById('sub-email').textContent=sub.email||'—';
  document.getElementById('sub-ends').textContent=sub.ends_at||'—';

  const launcher=data.launcher||{};
  document.getElementById('launcher-status').textContent=launcher.status||'Готов';
  document.getElementById('launcher-progress').style.width=(launcher.progress||0)+'%';

  const btn=document.getElementById('btn-launch');
  btn.disabled=!sub.has_access;
}

// Initial load
refreshStatus();
setInterval(refreshStatus,30000);
</script>
</body>
</html>
"""


class UnifiedHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, data: dict[str, Any], code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/refresh":
            update_subscription_status()
            with _STATE_LOCK:
                state = dict(_STATE)

            sub = state["subscription"]
            self._json({
                "subscription": {
                    "has_access": sub["has_access"],
                    "email": sub["email"],
                    "ends_at": format_date(sub["ends_at"]),
                },
                "launcher": state["launcher"],
            })

        elif path == "/api/launch":
            with _STATE_LOCK:
                has_access = _STATE["subscription"]["has_access"]

            if not has_access:
                self._json({"ok": False, "error": "Нет активной подписки"}, 403)
                return

            try:
                if HAS_CLIENT:
                    ok, msg = launch_payload(mode="launcher")
                    self._json({"ok": ok, "message": msg})
                else:
                    self._json({"ok": False, "error": "Модуль запуска недоступен"})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})

        elif path == "/api/account":
            app_url = resolve_app_url() if HAS_CLIENT else "https://nexus-web-production-13f1.up.railway.app"
            self._json({"url": f"{app_url}/account"})

        elif path == "/api/logs":
            log_path = Path(os.environ.get("APPDATA", ".")) / "Nexus" / "nexus_client.log"
            self._json({"path": str(log_path)})

        elif path == "/api/exit":
            self._json({"ok": True})
            threading.Thread(target=lambda: (time.sleep(0.5), os._exit(0)), daemon=True).start()

        else:
            self.send_error(404)


def start_server():
    """Запустить HTTP сервер"""
    server = http.server.HTTPServer(("127.0.0.1", PORT), UnifiedHandler)
    log(f"NEXUS Unified running on http://127.0.0.1:{PORT}")
    server.serve_forever()


def main():
    """Главная функция"""
    log("=== NEXUS Unified Client ===")

    # Обновляем статус подписки
    threading.Thread(target=update_subscription_status, daemon=True).start()

    # Запускаем сервер в фоне
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Ждем запуска сервера
    time.sleep(1)

    # Открываем браузер
    url = f"http://127.0.0.1:{PORT}"

    # Пытаемся открыть в нативном окне если есть pywebview
    try:
        import webview
        window = webview.create_window(
            "NEXUS 2099",
            url,
            width=UI_WIDTH,
            height=UI_HEIGHT,
            resizable=True,
            background_color="#000000",
        )
        webview.start()
    except ImportError:
        # Fallback на браузер
        webbrowser.open(url)
        log("Открыто в браузере. Нажми Ctrl+C для выхода.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log("Выход...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nВыход...")
        os._exit(0)
    except Exception as e:
        log(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        os._exit(1)
