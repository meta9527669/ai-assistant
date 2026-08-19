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
    from flask import Flask, request, Response, render_template_string
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
        app = Flask(__name__)

        @app.route("/")
        def mobile_page():
            return MOBILE_HTML

        @app.route("/subtitle")
        def subtitle_page():
            return SUBTITLE_HTML

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
<title>李亦禾</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    background: linear-gradient(180deg, #0a0e27 0%, #1a1f3a 100%);
    color: #e0e0e0; min-height: 100vh; overflow-x: hidden;
  }
  .header {
    background: rgba(255,255,255,0.05); padding: 16px 20px;
    text-align: center; position: sticky; top: 0; z-index: 10;
    border-bottom: 1px solid rgba(255,255,255,0.1);
  }
  .header h1 { font-size: 20px; color: #7ec8ff; }
  .header .status { font-size: 12px; color: #666; margin-top: 4px; }
  .chat {
    padding: 16px; padding-bottom: 120px;
    display: flex; flex-direction: column; gap: 10px;
  }
  .msg {
    max-width: 85%; padding: 12px 16px; border-radius: 16px;
    font-size: 16px; line-height: 1.5; word-break: break-all;
    animation: slideIn 0.3s ease;
  }
  .msg.user {
    align-self: flex-end; background: #2563eb; color: #fff;
    border-bottom-right-radius: 4px;
  }
  .msg.assistant {
    align-self: flex-start; background: rgba(255,255,255,0.1);
    border-bottom-left-radius: 4px;
  }
  .msg.status {
    align-self: center; background: transparent; color: #666;
    font-size: 13px; font-style: italic;
  }
  .msg .time { font-size: 10px; opacity: 0.5; margin-top: 4px; }
  @keyframes slideIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .input-bar {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: rgba(10,14,39,0.95); padding: 12px 16px;
    border-top: 1px solid rgba(255,255,255,0.1);
    display: flex; gap: 8px; align-items: center;
  }
  .input-bar input {
    flex: 1; background: rgba(255,255,255,0.1); border: none;
    border-radius: 24px; padding: 12px 18px; color: #fff;
    font-size: 16px; outline: none;
  }
  .input-bar input::placeholder { color: #555; }
  .input-bar button {
    background: #2563eb; border: none; border-radius: 50%;
    width: 44px; height: 44px; color: #fff;
    font-size: 20px; cursor: pointer; flex-shrink: 0;
  }
  .input-bar button:active { transform: scale(0.9); }
  .quick-bar {
    display: flex; gap: 8px; padding: 8px 16px;
    overflow-x: auto; white-space: nowrap;
  }
  .quick-btn {
    background: rgba(126,200,255,0.15); border: 1px solid rgba(126,200,255,0.3);
    border-radius: 16px; padding: 6px 14px; color: #7ec8ff;
    font-size: 13px; cursor: pointer; flex-shrink: 0;
  }
  .quick-btn:active { background: rgba(126,200,255,0.3); }
</style>
</head>
<body>
<div class="header">
  <h1>✨ 李亦禾</h1>
  <div class="status" id="status">已连接</div>
</div>
<div class="quick-bar">
  <button class="quick-btn" onclick="send('现在几点了')">几点了</button>
  <button class="quick-btn" onclick="send('今天天气怎么样')">天气</button>
  <button class="quick-btn" onclick="send('帮我打开浏览器')">打开浏览器</button>
  <button class="quick-btn" onclick="send('搜索今日新闻')">搜新闻</button>
  <button class="quick-btn" onclick="send('记一下今天很开心')">记一笔</button>
  <button class="quick-btn" onclick="send('今天有点累')">聊聊天</button>
</div>
<div class="chat" id="chat"></div>
<div class="input-bar">
  <input type="text" id="input" placeholder="跟李亦禾说点什么..."
    onkeydown="if(event.key==='Enter')doSend()">
  <button onclick="doSend()">➤</button>
</div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const statusEl = document.getElementById('status');

function addMsg(role, text, time) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = (role === 'user' ? '🗣 ' : role === 'assistant' ? '✨ ' : '') + text
    + '<div class="time">' + (time || '') + '</div>';
  chat.appendChild(div);
  window.scrollTo(0, document.body.scrollHeight);
}

function doSend() {
  const text = input.value.trim();
  if (!text) return;
  send(text);
  input.value = '';
}

function send(text) {
  fetch('/send', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text: text})
  });
}

const es = new EventSource('/stream');
es.onopen = function() { statusEl.textContent = '已连接'; statusEl.style.color = '#4ade80'; };
es.onerror = function() { statusEl.textContent = '连接中断...'; statusEl.style.color = '#f87171'; };
es.onmessage = function(e) {
  const msg = JSON.parse(e.data);
  addMsg(msg.role, msg.text, msg.timestamp);
};
</script>
</body>
</html>"""
