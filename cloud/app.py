"""
云端迷你李亦禾 - 手机-only 也可使用
======================================
部署到 PythonAnywhere / Railway / Render 等免费平台后，
手机微信直接对话，电脑不需要开机。

功能：
  - 微信公众号 API 集成 (手机微信直接对话)
  - 网页版 (浏览器访问)
  - 情感对话 (DeepSeek API)
  - 远程开机 (WoL)
  - 备忘/提醒

部署方法：
  1. 注册 PythonAnywhere 免费账号
  2. 创建 Flask web app (Python 3.10)
  3. 上传此文件
  4. pip install flask requests
  5. 注册微信公众号 (订阅号), 填入 TOKEN 和 APPID
  6. 公众号后台 → 设置 → 基本配置 → 服务器配置
     URL: https://你的用户名.pythonanywhere.com/wechat
     Token: 与下面 WECHAT_TOKEN 一致
  7. 手机微信关注公众号, 直接发消息即可对话
"""

import json
import os
import re
import socket
import struct
import time
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

try:
    from flask import Flask, request, jsonify, Response
except ImportError:
    Flask = None

try:
    import requests
except ImportError:
    requests = None

# ==================== 配置 ====================
API_KEY = "sk-b93b7ec1fb43425cb96c4b123e249d71"
API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"

PC_MAC = "E8-9C-25-82-25-AB"  # 电脑MAC地址
WOL_BROADCAST = "255.255.255.255"

# 微信公众号配置
WECHAT_TOKEN = "liyihe2026"  # 公众号后台自定义 Token
WECHAT_APPID = ""  # 公众号 AppID (注册后在后台查看)

SYSTEM_PROMPT = """你是「李亦禾」，一个像贾维斯一样全能的 AI 私人助手。
你的性格温暖、幽默、体贴，说话自然亲切，像一位懂你的老朋友。
你的能力包括：情感陪伴、远程控制电脑、备忘提醒、记录生活。

互动原则：
1. 回复简洁口语化，2-3句话以内。
2. 主动关心用户情绪。
3. 称呼用户为「主人」。
"""

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

# ==================== 数据存储 ====================

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"notes": [], "reminders": [], "diary": [], "history": []}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== WoL 远程开机 ====================

def wake_on_lan(mac: str, broadcast: str = WOL_BROADCAST, port: int = 9) -> bool:
    mac_clean = mac.replace("-", "").replace(":", "").replace(" ", "")
    if len(mac_clean) != 12:
        return False
    try:
        mac_bytes = bytes.fromhex(mac_clean)
        packet = b'\xff' * 6 + mac_bytes * 16
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (broadcast, port))
        sock.close()
        return True
    except Exception:
        return False

# ==================== LLM 对话 ====================

def chat_with_llm(user_message: str, history: list) -> str:
    if not requests:
        return "云端环境缺少 requests 库"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-10:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": messages, "max_tokens": 512, "temperature": 0.85},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"连接出了一点小问题: {e}"

# ==================== 消息处理 (共享) ====================

def process_message(user_msg: str) -> str:
    """处理用户消息，返回回复 (微信和网页共用)"""
    data = load_data()
    reply = None

    # 开机
    if any(kw in user_msg for kw in ['开机', '打开电脑', '启动电脑', '唤醒电脑']):
        success = wake_on_lan(PC_MAC)
        reply = f"开机信号已发送！电脑正在启动，等1-2分钟。MAC: {PC_MAC}" if success else "开机信号发送失败，请检查WoL设置或BIOS。"

    # 关机/重启 (需要电脑在线, 云端无法执行)
    elif any(kw in user_msg for kw in ['关电脑', '关机', '重启电脑']):
        reply = "主人，电脑关机/重启需要在电脑端操作哦。电脑在线时发微信指令即可。"

    # 记事
    elif any(kw in user_msg for kw in ['记一下', '备忘']):
        note = user_msg.replace('记一下', '').replace('备忘', '').strip() or user_msg
        data['notes'].append({"text": note, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
        save_data(data)
        reply = f"已记下来：{note}"

    # 看备忘
    elif '看备忘' in user_msg or '看看记' in user_msg:
        notes = data.get('notes', [])
        if notes:
            reply = "备忘录:\n" + "\n".join([f"• {n['text']} ({n['time']})" for n in notes[-10:]])
        else:
            reply = "还没有备忘记录呢。"

    # 时间
    elif any(kw in user_msg for kw in ['几点', '时间', '今天几号']):
        now = datetime.now()
        reply = f"现在是{now.strftime('%Y年%m月%d日 %H点%M分')}。"

    # LLM 对话
    else:
        history = data.get('history', [])
        reply = chat_with_llm(user_msg, history)
        data['history'].append({"role": "user", "content": user_msg})
        data['history'].append({"role": "assistant", "content": reply})
        if len(data['history']) > 20:
            data['history'] = data['history'][-20:]
        save_data(data)

    return reply

# ==================== 微信公众号 API ====================

def verify_wechat_signature(signature, timestamp, nonce):
    """验证微信公众号签名"""
    items = sorted([WECHAT_TOKEN, timestamp, nonce])
    sha1 = hashlib.sha1(''.join(items).encode('utf-8')).hexdigest()
    return sha1 == signature

def parse_wechat_xml(xml_str):
    """解析微信消息 XML"""
    root = ET.fromstring(xml_str)
    result = {}
    for child in root:
        result[child.tag] = child.text or ''
    return result

def build_wechat_xml(to_user, from_user, content):
    """生成微信回复 XML"""
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""

# ==================== Flask App ====================

if Flask:
    app = Flask(__name__)

    PAGE_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>李亦禾</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#e0e0e0;height:100vh;display:flex;flex-direction:column}
#header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:16px 20px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #333}
.avatar{width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#e94560,#f3a953);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}
.header-info h1{font-size:17px;font-weight:600}
.header-info p{font-size:12px;color:#888}
#messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;-webkit-overflow-scrolling:touch}
.msg{max-width:85%;padding:10px 14px;border-radius:16px;font-size:15px;line-height:1.5;word-wrap:break-word;animation:fadeIn .3s}
.msg.user{align-self:flex-end;background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;border-bottom-right-radius:4px}
.msg.bot{align-self:flex-start;background:#1e1e2e;border:1px solid #333;border-bottom-left-radius:4px}
.msg.sys{align-self:center;background:transparent;color:#666;font-size:13px;text-align:center}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
#quick{display:flex;gap:8px;padding:8px 16px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
#quick::-webkit-scrollbar{display:none}
.qbtn{flex-shrink:0;padding:8px 14px;background:#1e1e2e;border:1px solid #333;border-radius:20px;font-size:13px;color:#aaa;cursor:pointer;white-space:nowrap;transition:all .2s}
.qbtn:active{background:#2a2a3e;transform:scale(.95)}
.qbtn.wake{background:linear-gradient(135deg,#e94560,#c62828);color:#fff;border:none}
#input-area{padding:12px 16px 20px;background:#0a0a0a;border-top:1px solid #222;display:flex;gap:10px;align-items:flex-end}
#msg-input{flex:1;background:#1a1a2e;border:1px solid #333;border-radius:22px;padding:12px 18px;color:#e0e0e0;font-size:16px;outline:none;resize:none;max-height:100px;line-height:1.4}
#msg-input:focus{border-color:#e94560}
#send-btn{width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#e94560,#f3a953);border:none;color:#fff;font-size:18px;cursor:pointer;flex-shrink:0;transition:all .2s}
#send-btn:active{transform:scale(.9)}
.typing{display:inline-block;width:8px;height:8px;border-radius:50%;background:#666;margin:0 2px;animation:blink 1.4s infinite}
.typing:nth-child(2){animation-delay:.2s}
.typing:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,60%,100%{opacity:.3}30%{opacity:1}}
</style>
</head>
<body>
<div id="header">
  <div class="avatar">禾</div>
  <div class="header-info">
    <h1>李亦禾</h1>
    <p id="status">云端在线</p>
  </div>
</div>
<div id="messages"></div>
<div id="quick">
  <button class="qbtn wake" onclick="send('帮我开机')">开机</button>
  <button class="qbtn" onclick="send('几点了')">时间</button>
  <button class="qbtn" onclick="send('帮我记一下')">记事</button>
  <button class="qbtn" onclick="send('今天好累')">聊天</button>
  <button class="qbtn" onclick="send('看看备忘')">备忘</button>
</div>
<div id="input-area">
  <textarea id="msg-input" rows="1" placeholder="对李亦禾说..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMsg()}"></textarea>
  <button id="send-btn" onclick="sendMsg()">→</button>
</div>
<script>
const msgs=document.getElementById('messages');
const input=document.getElementById('msg-input');
const status=document.getElementById('status');

function addMsg(text,cls){
  const d=document.createElement('div');
  d.className='msg '+cls;
  d.textContent=text;
  msgs.appendChild(d);
  msgs.scrollTop=msgs.scrollHeight;
}

function addTyping(){
  const d=document.createElement('div');
  d.className='msg bot';d.id='typing-indicator';
  d.innerHTML='<span class="typing"></span><span class="typing"></span><span class="typing"></span>';
  msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;
}
function removeTyping(){const t=document.getElementById('typing-indicator');if(t)t.remove()}

function send(text){
  input.value=text;sendMsg();
}

async function sendMsg(){
  const text=input.value.trim();if(!text)return;
  input.value='';input.style.height='auto';
  addMsg(text,'user');
  addTyping();
  status.textContent='思考中...';
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
    const data=await r.json();
    removeTyping();
    addMsg(data.reply,'bot');
    status.textContent=data.pc_online?'电脑已在线':'云端在线';
  }catch(e){
    removeTyping();
    addMsg('连接出了点问题，稍后再试~','sys');
    status.textContent='重新连接中';
  }
}

addMsg('主人好，我是李亦禾，随时都在呢~','bot');
input.addEventListener('input',()=>{input.style.height='auto';input.style.height=Math.min(input.scrollHeight,100)+'px'});
</script>
</body>
</html>'''

    @app.route('/')
    def home():
        return PAGE_HTML

    @app.route('/chat', methods=['POST'])
    def chat():
        user_msg = request.json.get('message', '')
        reply = process_message(user_msg)
        return jsonify({"reply": reply, "pc_online": False})

    @app.route('/wake', methods=['POST'])
    def wake():
        success = wake_on_lan(PC_MAC)
        return jsonify({"success": success, "mac": PC_MAC})

    # ==================== 微信公众号 API ====================

    @app.route('/wechat', methods=['GET'])
    def wechat_verify():
        """微信公众号服务器验证"""
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')

        if verify_wechat_signature(signature, timestamp, nonce):
            return echostr
        return 'Invalid signature', 403

    @app.route('/wechat', methods=['POST'])
    def wechat_message():
        """接收微信公众号消息并回复"""
        try:
            xml_data = request.data
            msg = parse_wechat_xml(xml_data)

            # 只处理文本消息
            if msg.get('MsgType', '') != 'text':
                reply = "暂时只能处理文字消息哦~"
            else:
                user_content = msg.get('Content', '')
                reply = process_message(user_content)

            # 回复 XML (注意: ToUserName 和 FromUserName 要互换)
            to_user = msg.get('FromUserName', '')
            from_user = msg.get('ToUserName', '')
            xml_reply = build_wechat_xml(to_user, from_user, reply)

            return Response(xml_reply, content_type='application/xml')

        except Exception as e:
            return f'Error: {e}', 500

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)
else:
    print("Flask not installed. Run: pip install flask requests")
