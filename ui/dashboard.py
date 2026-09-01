# -*- coding: utf-8 -*-
"""
Elívea — Web Dashboard
===============================
Painel de controle web para monitorar e configurar a IA.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional


class WebDashboard:
    """Dashboard web leve para monitoramento."""

    _server: Optional[HTTPServer] = None
    _thread: Optional[threading.Thread] = None
    _port = 8080

    @classmethod
    def start(cls, port: int = 8080):
        """Inicia o servidor web do dashboard."""
        if cls._server:
            return
        cls._port = port
        handler = _create_handler()
        try:
            cls._server = HTTPServer(("0.0.0.0", port), handler)
            cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
            cls._thread.start()
            print(f"[Dashboard] Rodando em http://localhost:{port}")
        except Exception as e:
            print(f"[Dashboard] Erro ao iniciar: {e}")

    @classmethod
    def stop(cls):
        if cls._server:
            cls._server.shutdown()
            cls._server = None

    @classmethod
    def get_url(cls) -> str:
        return f"http://localhost:{cls._port}"


def _create_handler():
    """Cria o handler do HTTP server."""

    class DashboardHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(_get_dashboard_html().encode("utf-8"))
            elif self.path == "/api/status":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                data = _get_api_status()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            elif self.path == "/api/system":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                data = _get_system_data()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    return DashboardHandler


def _get_api_status() -> dict:
    try:
        from datetime import datetime
        return {
            "status": "online",
            "uptime": datetime.now().isoformat(),
            "version": "1.0.0",
        }
    except Exception:
        return {"status": "error"}


def _get_system_data() -> dict:
    try:
        from modules.monitor import SystemMonitor
        return {
            "cpu": SystemMonitor.get_cpu_usage(),
            "memory": SystemMonitor.get_memory_info(),
            "disk": SystemMonitor.get_disk_info(),
            "network": SystemMonitor.get_network_info(),
        }
    except Exception:
        return {"error": "Modulo de monitoramento nao disponivel"}


def _get_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Elívea - Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px 30px;border-bottom:2px solid #c8a84e}
.header h1{color:#c8a84e;font-size:24px}
.header p{color:#888;font-size:14px}
.container{max-width:1200px;margin:0 auto;padding:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-top:20px}
.card{background:#12121a;border:1px solid #2a2a3a;border-radius:12px;padding:20px}
.card h3{color:#c8a84e;margin-bottom:12px;font-size:16px}
.stat{display:flex;justify-content:space-between;margin:8px 0;padding:6px 0;border-bottom:1px solid #1a1a2a}
.stat-label{color:#888}
.stat-value{color:#e0e0e0;font-weight:600}
.bar{width:100%;height:8px;background:#1a1a2a;border-radius:4px;margin-top:6px}
.bar-fill{height:100%;border-radius:4px;transition:width 0.5s}
.bar-cpu{background:linear-gradient(90deg,#4ade80,#f59e0b,#ef4444)}
.bar-mem{background:linear-gradient(90deg,#60a5fa,#8b5cf6,#ec4899)}
.bar-disk{background:linear-gradient(90deg,#34d399,#06b6d4,#3b82f6)}
.refresh{background:#c8a84e;color:#0a0a0f;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:600;margin-top:10px}
.refresh:hover{background:#d4b85e}
#timestamp{color:#666;font-size:12px;margin-top:10px}
</style>
</head>
<body>
<div class="header">
<h1>&#10024; Elívea - Dashboard</h1>
<p>Painel de monitoramento em tempo real</p>
</div>
<div class="container">
<div class="grid">
<div class="card">
<h3>&#128187; CPU</h3>
<div class="stat"><span class="stat-label">Uso</span><span class="stat-value" id="cpu-percent">--</span></div>
<div class="stat"><span class="stat-label">Nucleos</span><span class="stat-value" id="cpu-cores">--</span></div>
<div class="bar"><div class="bar-fill bar-cpu" id="cpu-bar" style="width:0%"></div></div>
</div>
<div class="card">
<h3>&#128190; Memoria RAM</h3>
<div class="stat"><span class="stat-label">Uso</span><span class="stat-value" id="mem-used">--</span></div>
<div class="stat"><span class="stat-label">Total</span><span class="stat-value" id="mem-total">--</span></div>
<div class="bar"><div class="bar-fill bar-mem" id="mem-bar" style="width:0%"></div></div>
</div>
<div class="card">
<h3>&#128193; Disco</h3>
<div id="disk-info">Carregando...</div>
</div>
<div class="card">
<h3>&#127760; Rede</h3>
<div class="stat"><span class="stat-label">Enviado</span><span class="stat-value" id="net-sent">--</span></div>
<div class="stat"><span class="stat-label">Recebido</span><span class="stat-value" id="net-recv">--</span></div>
</div>
</div>
<button class="refresh" onclick="fetchData()">Atualizar</button>
<div id="timestamp"></div>
</div>
<script>
async function fetchData(){
try{
const r=await fetch('/api/system');
const d=await r.json();
if(d.cpu){document.getElementById('cpu-percent').textContent=d.cpu.percent+'%';document.getElementById('cpu-cores').textContent=d.cpu.cores;document.getElementById('cpu-bar').style.width=d.cpu.percent+'%'}
if(d.memory){document.getElementById('mem-used').textContent=d.memory.used_gb+' GB';document.getElementById('mem-total').textContent=d.memory.total_gb+' GB';document.getElementById('mem-bar').style.width=d.memory.percent+'%'}
if(d.disk&&d.disk.length>0){let h='';d.disk.forEach(di=>{h+='<div class="stat"><span class="stat-label">'+di.device+'</span><span class="stat-value">'+di.used_gb+'/'+di.total_gb+' GB ('+di.percent+'%)</span></div>'});document.getElementById('disk-info').innerHTML=h}
if(d.network){document.getElementById('net-sent').textContent=d.network.bytes_sent_mb+' MB';document.getElementById('net-recv').textContent=d.network.bytes_recv_mb+' MB'}
document.getElementById('timestamp').textContent='Atualizado: '+new Date().toLocaleString('pt-BR')
}catch(e){console.error(e)}
}
fetchData();setInterval(fetchData,5000);
</script>
</body>
</html>"""
