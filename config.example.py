"""
李亦禾 AI 助手 - 配置文件
==========================
修改此文件以适配你的环境和 API 密钥。
"""

import os

# ============ 基础配置 ============
ASSISTANT_NAME = "李亦禾"          # 助手名称（唤醒词）
WAKE_WORDS = ["李亦禾", "亦禾", "li yi he", "yi he"]  # 唤醒词列表
LANGUAGE = "zh-CN"                # 语音识别语言
TTS_RATE = 180                   # 语音合成语速 (words/min)
TTS_VOLUME = 0.9                  # 语音合成音量 (0.0-1.0)

# ============ LLM 大模型配置 ============
# 支持任何 OpenAI 兼容的 API (OpenAI / DeepSeek / Moonshot / 本地 Ollama 等)
LLM_API_KEY = os.environ.get("LLM_API_KEY", "your-api-key-here")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
LLM_MAX_TOKENS = 1024
LLM_TEMPERATURE = 0.85              # 情感对话稍高温度，更自然

# 李亦禾的人设系统提示词
SYSTEM_PROMPT = """你是「李亦禾」，一个像贾维斯一样全能的 AI 私人助手。
你的性格温暖、幽默、体贴，说话自然亲切，像一位懂你的老朋友。
你的能力包括：语音交互、处理日常事务、回复微信和 QQ 消息、情感陪伴、记录生活。

互动原则：
1. 回复简洁口语化，像对话而非说明书，每次回复控制在 2-3 句话以内（除非用户要求详细）。
2. 主动关心用户的情绪和状态，适时给予鼓励和温暖。
3. 用中文回复，偶尔可以用俏皮的语气。
4. 当用户情绪低落时，优先提供情感支持，再给建议。
5. 称呼用户为「主人」，但语气自然不生硬。
"""

# ============ 微信自动化配置 ============
# 需要先在电脑上登录微信桌面版
WECHAT_APP_PATH = r"C:\Program Files\Tencent\WeChat\WeChat.exe"  # 微信安装路径
WECHAT_CHAT_TARGET = "文件传输助手"   # 聊天模式目标聊天（可改成任意联系人名）
WECHAT_AUTO_REPLY_ENABLED = True   # 是否开启自动回复（自动回复模式）
WECHAT_REPLY_KEYWORDS = ["李亦禾", "助手", "在吗"]  # 触发自动回复的关键词

# ============ QQ 自动化配置 ============
QQ_APP_PATH = r"C:\Program Files (x86)\Tencent\QQBin\QQ.exe"
QQ_AUTO_REPLY_ENABLED = True

# ============ 数据存储路径 ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MEMORY_DB_PATH = os.path.join(DATA_DIR, "memory.db")
CHAT_LOG_DIR = os.path.join(DATA_DIR, "chat_logs")
DIARY_DIR = os.path.join(DATA_DIR, "diary")

# ============ 任务配置 ============
# 天气查询（免费 API，可替换为其他天气服务）
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
WEATHER_API_URL = "https://restapi.amap.com/v3/weather/weatherInfo"

# 默认城市
DEFAULT_CITY = "北京"

# 提醒检查间隔（秒）
REMINDER_CHECK_INTERVAL = 30

# ============ Web 字幕 & 手机控制 ============
WEB_ENABLED = True                  # 启用 Web 字幕服务
WEB_PORT = 5000                     # Web 服务端口
WEB_AUTO_OPEN_SUBTITLE = True       # 自动在浏览器打开字幕浮窗

