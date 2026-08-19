"""
字幕浮窗模块 - 桌面屏幕字幕 + 手机网页控制

通过 Flask Web 服务器实现：
  - /subtitle  桌面字幕浮窗页面（浏览器全屏，底部字幕条）
  - /mobile    手机控制页面（字幕显示 + 文字输入 + 快捷指令）
  - /stream    SSE 实时推送对话内容
  - /send      接收手机发来的文字指令
"""

import json
import queue
import threading
import time
import socket
from datetime import datetime

try:
    from flask import Flask, request, Response, render_template_string, send_from_directory
except ImportError:
    Flask = None

import config


class SubtitleServer:
    """字幕浮窗 + 手机 Web 控制服务器"""

    def __init__(self, on_message=None):
        self.on_message = on_message  # 回调：手机发来消息时调用
        self.message_queue: queue.Queue = queue.Queue()
        self.history: list[dict] = []
        self.max_history = 50
        self.app = None
        self.thread = None
        self.running = False
        self.port = config.WEB_PORT
        self.host = "0.0.0.0"
        self.wechat_bot = None  # 微信机器人引用（后设置）

    def set_wechat_bot(self, bot):
        """设置微信机器人引用，用于手机端微信操作"""
        self.wechat_bot = bot

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def push(self, role: str, text: str):
        """推送一条消息到所有客户端"""
        msg = {
            "role": role,
            "text": text,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        self.history.append(msg)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self.message_queue.put(msg)

    def push_user(self, text: str):
        self.push("user", text)

    def push_assistant(self, text: str):
        self.push("assistant", text)

    def push_status(self, text: str):
        self.push("status", text)

    def _create_app(self):
        import os
        static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
        app = Flask(__name__, static_folder=static_dir, static_url_path="/static")

        @app.route("/")
        def mobile_page():
            return MOBILE_HTML

        @app.route("/subtitle")
        def subtitle_page():
            return SUBTITLE_HTML

        @app.route("/manifest.json")
        def manifest():
            return Response(MANIFEST_JSON, mimetype="application/manifest+json")

        @app.route("/sw.js")
        def service_worker():
            return Response(SERVICE_WORKER_JS, mimetype="application/javascript")

        @app.route("/stream")
        def stream():
            def event_stream():
                last_index = 0
                while self.running:
                    try:
                        msg = self.message_queue.get(timeout=1)
                        yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        yield ": keepalive\n\n"

            return Response(
                event_stream(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                },
            )

        @app.route("/history")
        def history():
            return json.dumps(self.history, ensure_ascii=False)

        @app.route("/send", methods=["POST"])
        def send():
            data = request.get_json(force=True)
            text = data.get("text", "").strip()
            if text and self.on_message:
                self.push_user(text)
                self.on_message(text)
            return json.dumps({"ok": True})

        @app.route("/wechat/messages")
        def wechat_messages():
            if self.wechat_bot:
                return json.dumps(self.wechat_bot.get_messages(), ensure_ascii=False)
            return json.dumps([])

        @app.route("/wechat/send", methods=["POST"])
        def wechat_send():
            data = request.get_json(force=True)
            contact = data.get("contact", "").strip()
            message = data.get("message", "").strip()
            if contact and message and self.wechat_bot:
                self.wechat_bot.queue_send(contact, message)
                return json.dumps({"ok": True, "msg": f"已加入发送队列: {contact}"})
            return json.dumps({"ok": False, "msg": "联系人或消息为空"})

        @app.route("/wechat/auto-reply", methods=["POST"])
        def wechat_auto_reply():
            data = request.get_json(force=True)
            enabled = data.get("enabled")
            if self.wechat_bot:
                result = self.wechat_bot.toggle_auto_reply(enabled)
                self.push_status(f"微信自动回复: {'已开启' if result else '已关闭'}")
                return json.dumps({"ok": True, "auto_reply": result})
            return json.dumps({"ok": False})

        @app.route("/wechat/status")
        def wechat_status():
            if self.wechat_bot:
                return json.dumps({
                    "running": self.wechat_bot.running,
                    "auto_reply": self.wechat_bot.auto_reply,
                    "message_count": len(self.wechat_bot.get_messages()),
                })
            return json.dumps({"running": False, "auto_reply": False, "message_count": 0})

        return app

    def start(self):
        if Flask is None:
            print("[字幕] Flask 未安装，请运行 pip install flask")
            return

        self.app = self._create_app()
        self.running = True
        local_ip = self._get_local_ip()
        print(f"\n{'='*50}")
        print(f"  李亦禾 Web 服务已启动")
        print(f"  手机访问:  http://{local_ip}:{self.port}")
        print(f"  字幕浮窗:  http://{local_ip}:{self.port}/subtitle")
        print(f"  本机访问:  http://127.0.0.1:{self.port}")
        print(f"{'='*50}\n")

        self.thread = threading.Thread(
            target=lambda: self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True,
            ),
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.running = False


# ============ PWA Manifest ============
MANIFEST_JSON = """{
  "name": "李亦禾 AI 助手",
  "short_name": "李亦禾",
  "description": "你的私人 AI 助手 - 语音控制、事务处理、消息回复、情感陪伴",
  "start_url": "/",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#0a0e27",
  "theme_color": "#0a0e27",
  "icons": [
    {
      "src": "/static/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/static/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/static/icons/icon-maskable.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ]
}"""

# ============ Service Worker ============
SERVICE_WORKER_JS = """
const CACHE_NAME = 'liyihe-v1';
const ASSETS = ['/static/icons/icon-192.png', '/static/icons/icon-512.png'];

self.addEventListener('install', function(e) {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS).catch(()=>{})));
});

self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', function(e) {
  if (e.request.url.includes('/stream') || e.request.url.includes('/send')) {
    return;
  }
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
"""


# ============ 桌面字幕浮窗 HTML ============
SUBTITLE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>李亦禾 - 字幕</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: rgba(0, 0, 0, 0.75);
    overflow: hidden;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 20px;
  }
  .subtitle-bar {
    text-align: center;
    padding: 16px 32px;
    min-height: 80px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    justify-content: center;
  }
  .line {
    font-size: 28px;
    line-height: 1.5;
    color: #fff;
    text-shadow: 0 2px 8px rgba(0,0,0,0.8);
    animation: fadeIn 0.3s ease;
    word-break: break-all;
  }
  .line.user { color: #7ec8ff; }
  .line.assistant { color: #ffd97a; }
  .line.status { color: #aaa; font-size: 18px; font-style: italic; }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .hint {
    position: fixed; top: 10px; right: 15px;
    color: #555; font-size: 13px;
  }
</style>
</head>
<body>
<div class="hint">李亦禾字幕 · 保持此窗口打开</div>
<div class="subtitle-bar" id="bar"></div>
<script>
const es = new EventSource('/stream');
es.onmessage = function(e) {
  const msg = JSON.parse(e.data);
  const bar = document.getElementById('bar');
  const line = document.createElement('div');
  line.className = 'line ' + msg.role;
  const prefix = msg.role === 'user' ? '🗣 ' : msg.role === 'assistant' ? '✨ ' : '';
  line.textContent = prefix + msg.text;
  bar.appendChild(line);
  while (bar.children.length > 4) bar.removeChild(bar.firstChild);
  window.scrollTo(0, document.body.scrollHeight);
};
</script>
</body>
</html>"""


# ============ 手机控制页面 HTML ============
MOBILE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="李亦禾">
<meta name="theme-color" content="#0a0e27">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
<link rel="icon" type="image/png" href="/static/icons/icon-192.png">
<title>李亦禾</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  body { font-family:"PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(180deg,#0a0e27 0%,#1a1f3a 100%); color:#e0e0e0; min-height:100vh; overflow-x:hidden; }
  /* Tab Bar */
  .tab-bar { position:sticky; top:0; z-index:20; display:flex; background:rgba(10,14,39,0.95); border-bottom:1px solid rgba(255,255,255,0.1); }
  .tab-btn { flex:1; padding:14px 0; text-align:center; font-size:15px; color:#666; background:none; border:none; cursor:pointer; border-bottom:2px solid transparent; transition:all 0.2s; }
  .tab-btn.active { color:#7ec8ff; border-bottom-color:#7ec8ff; }
  /* Panels */
  .panel { display:none; }
  .panel.active { display:block; }
  /* Assistant Panel */
  .quick-bar { display:flex; gap:8px; padding:8px 16px; overflow-x:auto; white-space:nowrap; }
  .quick-btn { background:rgba(126,200,255,0.15); border:1px solid rgba(126,200,255,0.3); border-radius:16px; padding:6px 14px; color:#7ec8ff; font-size:13px; cursor:pointer; flex-shrink:0; }
  .quick-btn:active { background:rgba(126,200,255,0.3); }
  .chat { padding:16px; padding-bottom:120px; display:flex; flex-direction:column; gap:10px; }
  .msg { max-width:85%; padding:12px 16px; border-radius:16px; font-size:16px; line-height:1.5; word-break:break-all; animation:slideIn 0.3s ease; }
  .msg.user { align-self:flex-end; background:#2563eb; color:#fff; border-bottom-right-radius:4px; }
  .msg.assistant { align-self:flex-start; background:rgba(255,255,255,0.1); border-bottom-left-radius:4px; }
  .msg.status { align-self:center; background:transparent; color:#666; font-size:13px; font-style:italic; }
  .msg.wechat { align-self:flex-start; background:rgba(0,200,83,0.15); border:1px solid rgba(0,200,83,0.3); border-bottom-left-radius:4px; }
  .msg .time { font-size:10px; opacity:0.5; margin-top:4px; }
  @keyframes slideIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
  .input-bar { position:fixed; bottom:0; left:0; right:0; background:rgba(10,14,39,0.95); padding:12px 16px; border-top:1px solid rgba(255,255,255,0.1); display:flex; gap:8px; align-items:center; }
  .input-bar input { flex:1; background:rgba(255,255,255,0.1); border:none; border-radius:24px; padding:12px 18px; color:#fff; font-size:16px; outline:none; }
  .input-bar input::placeholder { color:#555; }
  .input-bar button { background:#2563eb; border:none; border-radius:50%; width:44px; height:44px; color:#fff; font-size:20px; cursor:pointer; flex-shrink:0; }
  .input-bar button:active { transform:scale(0.9); }
  /* WeChat Panel */
  .wc-status { padding:16px 20px; border-bottom:1px solid rgba(255,255,255,0.05); }
  .wc-status .row { display:flex; justify-content:space-between; align-items:center; padding:6px 0; }
  .wc-status .label { color:#666; font-size:14px; }
  .wc-status .val { color:#7ec8ff; font-size:14px; }
  .switch { position:relative; width:48px; height:28px; }
  .switch input { opacity:0; width:0; height:0; }
  .slider { position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background:#333; border-radius:14px; transition:0.3s; }
  .slider:before { content:""; position:absolute; height:20px; width:20px; left:4px; bottom:4px; background:#fff; border-radius:50%; transition:0.3s; }
  input:checked + .slider { background:#22c55e; }
  input:checked + .slider:before { transform:translateX(20px); }
  .wc-list { padding:16px; padding-bottom:200px; }
  .wc-msg { display:flex; margin-bottom:12px; animation:slideIn 0.3s ease; }
  .wc-msg.out { flex-direction:row-reverse; }
  .wc-bubble { max-width:75%; padding:10px 14px; border-radius:14px; font-size:15px; line-height:1.4; word-break:break-all; }
  .wc-msg.in .wc-bubble { background:rgba(255,255,255,0.1); border-bottom-left-radius:4px; }
  .wc-msg.out .wc-bubble { background:#07c160; color:#fff; border-bottom-right-radius:4px; }
  .wc-meta { font-size:11px; color:#666; margin-bottom:3px; }
  .wc-msg.out .wc-meta { text-align:right; }
  .wc-send { position:fixed; bottom:0; left:0; right:0; background:rgba(10,14,39,0.95); padding:12px 16px; border-top:1px solid rgba(255,255,255,0.1); display:flex; flex-direction:column; gap:8px; }
  .wc-send-row { display:flex; gap:8px; }
  .wc-send input { flex:1; background:rgba(255,255,255,0.1); border:none; border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; }
  .wc-send input::placeholder { color:#555; }
  .wc-send button { background:#07c160; border:none; border-radius:10px; padding:10px 20px; color:#fff; font-size:14px; cursor:pointer; white-space:nowrap; }
  .wc-send button:active { transform:scale(0.95); }
  .wc-empty { text-align:center; color:#555; padding:40px 20px; font-size:14px; }
</style>
</head>
<body>

<!-- Tab Bar -->
<div class="tab-bar">
  <button class="tab-btn active" onclick="switchTab('assistant')">✨ 助手</button>
  <button class="tab-btn" onclick="switchTab('wechat')">💬 微信</button>
</div>

<!-- Assistant Panel -->
<div class="panel active" id="panel-assistant">
  <div class="quick-bar">
    <button class="quick-btn" onclick="sendMsg('现在几点了')">几点了</button>
    <button class="quick-btn" onclick="sendMsg('今天天气怎么样')">天气</button>
    <button class="quick-btn" onclick="sendMsg('帮我打开浏览器')">打开浏览器</button>
    <button class="quick-btn" onclick="sendMsg('搜索今日新闻')">搜新闻</button>
    <button class="quick-btn" onclick="sendMsg('记一下今天很开心')">记一笔</button>
    <button class="quick-btn" onclick="sendMsg('今天有点累')">聊聊天</button>
  </div>
  <div class="chat" id="chat"></div>
  <div class="input-bar">
    <input type="text" id="input" placeholder="跟李亦禾说点什么..." onkeydown="if(event.key==='Enter')doSend()">
    <button onclick="doSend()">➤</button>
  </div>
</div>

<!-- WeChat Panel -->
<div class="panel" id="panel-wechat">
  <div class="wc-status">
    <div class="row">
      <span class="label">微信监听</span>
      <span class="val" id="wc-running">检测中...</span>
    </div>
    <div class="row">
      <span class="label">自动回复</span>
      <label class="switch">
        <input type="checkbox" id="wc-auto-reply" onchange="toggleAutoReply(this.checked)">
        <span class="slider"></span>
      </label>
    </div>
    <div class="row">
      <span class="label">消息数</span>
      <span class="val" id="wc-count">0</span>
    </div>
  </div>
  <div class="wc-list" id="wc-list">
    <div class="wc-empty">暂无微信消息</div>
  </div>
  <div class="wc-send">
    <div class="wc-send-row">
      <input type="text" id="wc-contact" placeholder="联系人姓名">
    </div>
    <div class="wc-send-row">
      <input type="text" id="wc-message" placeholder="输入消息内容..." onkeydown="if(event.key==='Enter')wcSend()">
      <button onclick="wcSend()">发送</button>
    </div>
  </div>
</div>

<script>
// Tab switching
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  document.querySelectorAll('.panel').forEach(function(p) { p.classList.remove('active'); });
  event.target.classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
}

// Assistant chat
const chat = document.getElementById('chat');
const input = document.getElementById('input');

function addMsg(role, text, time) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = (role === 'user' ? '🗣 ' : role === 'assistant' ? '✨ ' : role === 'wechat' ? '💬 ' : '') + text
    + '<div class="time">' + (time || '') + '</div>';
  chat.appendChild(div);
  window.scrollTo(0, document.body.scrollHeight);
}

function doSend() {
  const text = input.value.trim();
  if (!text) return;
  sendMsg(text);
  input.value = '';
}

function sendMsg(text) {
  fetch('/send', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:text}) });
}

const es = new EventSource('/stream');
es.onmessage = function(e) {
  const msg = JSON.parse(e.data);
  addMsg(msg.role, msg.text, msg.timestamp);
};

// WeChat
function loadWeChat() {
  fetch('/wechat/status').then(function(r) { return r.json(); }).then(function(s) {
    document.getElementById('wc-running').textContent = s.running ? '运行中' : '未启动';
    document.getElementById('wc-running').style.color = s.running ? '#4ade80' : '#f87171';
    document.getElementById('wc-auto-reply').checked = s.auto_reply;
    document.getElementById('wc-count').textContent = s.message_count;
  }).catch(function(){});

  fetch('/wechat/messages').then(function(r) { return r.json(); }).then(function(msgs) {
    const list = document.getElementById('wc-list');
    if (!msgs.length) { list.innerHTML = '<div class="wc-empty">暂无微信消息</div>'; return; }
    list.innerHTML = '';
    msgs.forEach(function(m) {
      const div = document.createElement('div');
      div.className = 'wc-msg ' + (m.direction === 'out' ? 'out' : 'in');
      div.innerHTML = '<div><div class="wc-meta">' + m.contact + ' · ' + m.timestamp + '</div><div class="wc-bubble">' + m.message + '</div></div>';
      list.appendChild(div);
    });
    list.scrollTop = list.scrollHeight;
  }).catch(function(){});
}

function toggleAutoReply(enabled) {
  fetch('/wechat/auto-reply', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({enabled:enabled}) });
}

function wcSend() {
  const contact = document.getElementById('wc-contact').value.trim();
  const message = document.getElementById('wc-message').value.trim();
  if (!contact || !message) { alert('请填写联系人和消息'); return; }
  fetch('/wechat/send', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({contact:contact,message:message}) })
    .then(function(r) { return r.json(); }).then(function(d) {
      if (d.ok) { document.getElementById('wc-message').value = ''; }
      else { alert(d.msg || '发送失败'); }
    });
}

// Auto-refresh WeChat every 3s
setInterval(loadWeChat, 3000);
loadWeChat();

// PWA
if ('serviceWorker' in navigator) { navigator.serviceWorker.register('/sw.js').catch(function(){}); }
let deferredPrompt;
window.addEventListener('beforeinstallprompt', function(e) {
  e.preventDefault(); deferredPrompt = e;
  const bar = document.createElement('div');
  bar.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#2563eb;color:#fff;text-align:center;padding:10px;font-size:14px;cursor:pointer;z-index:100;';
  bar.textContent = '点击安装「李亦禾」到桌面';
  bar.onclick = function() { deferredPrompt.prompt(); deferredPrompt = null; bar.remove(); };
  document.body.appendChild(bar);
  setTimeout(function() { if (bar.parentNode) bar.remove(); }, 10000);
});
</script>
</body>
</html>"""
