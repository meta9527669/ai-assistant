# 李亦禾 AI 助手

> 一个像贾维斯一样的私人 AI 助手，能语音控制、处理日常事务、回复微信和 QQ 消息、情感陪伴、记录生活。

## 功能一览

| 功能模块 | 说明 |
|---------|------|
| 语音控制 | 唤醒词识别 + 自然语言指令，说「李亦禾」即可唤醒 |
| 事务处理 | 时间/日期查询、天气、打开应用、网页搜索、提醒、备忘、截图、系统控制 |
| 消息回复 | 自动监听微信和 QQ 消息，用大模型生成得体回复 |
| 情感陪伴 | 基于 LLM 的对话系统，温暖幽默，主动关心你的情绪 |
| 生活记录 | 对话日志、备忘录、日记、提醒，基于 SQLite 持久化存储 |

## 快速开始

### 1. 环境要求

- Python 3.10+
- Windows 10/11（语音和微信/QQ 自动化功能依赖 Windows）
- 麦克风（语音模式）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

编辑 `config.py`，填入你的大模型 API Key：

```python
LLM_API_KEY = "your-api-key"
LLM_BASE_URL = "https://api.deepseek.com/v1"  # 或 OpenAI / Moonshot 等
LLM_MODEL = "deepseek-chat"
```

也可以用环境变量：

```bash
export LLM_API_KEY="your-key"
export LLM_BASE_URL="https://api.deepseek.com/v1"
export LLM_MODEL="deepseek-chat"
```

### 4. 运行

```bash
# 语音模式（需要麦克风）
python main.py

# 文本模式（无麦克风环境）
python main.py --text

# 仅微信消息监听
python main.py --wechat

# 仅QQ消息监听
python main.py --qq
```

## 项目结构

```
liyihe-assistant/
├── main.py                 # 入口
├── config.py               # 配置（API Key、人设、路径等）
├── requirements.txt        # 依赖
├── core/
│   ├── assistant.py        # 主控调度器
│   ├── voice.py            # 语音识别(STT) + 语音合成(TTS)
│   ├── brain.py            # LLM 对话与情感陪伴
│   ├── tasks.py            # 基础事务指令处理
│   └── memory.py           # 记忆系统（SQLite）
├── platforms/
│   ├── wechat.py           # 微信消息自动化
│   └── qq.py               # QQ 消息自动化
└── data/                   # 运行时数据（自动创建）
    ├── memory.db           # SQLite 数据库
    ├── chat_logs/          # 每日对话日志
    └── diary/               # 日记文件
```

## 使用示例

### 语音指令

- 「李亦禾，现在几点了」
- 「李亦禾，今天天气怎么样」
- 「李亦禾，帮我打开浏览器」
- 「李亦禾，搜索 Python 教程」
- 「李亦禾，10分钟后提醒我开会」
- 「李亦禾，记一下明天要买牛奶」
- 「李亦禾，今天有点累...」（情感陪伴对话）

### 微信/QQ 自动回复

启动 `python main.py --wechat` 后，李亦禾会监听微信消息。
当消息中包含「李亦禾」「助手」「在吗」等关键词时，会自动用大模型生成回复。

## 支持的大模型

任何 OpenAI 兼容的 API 均可使用：

- DeepSeek（默认，性价比高）
- OpenAI GPT
- Moonshot Kimi
- 本地 Ollama（设 `LLM_BASE_URL=http://localhost:11434/v1`）

## 技术说明

- **语音识别**：Google Web Speech API + 离线 Sphinx 备选
- **语音合成**：pyttsx3 本地引擎
- **微信/QQ**：通过 uiautomation / pyautogui 模拟桌面操作（无官方 API 方案）
- **记忆系统**：SQLite 存储对话、备忘、提醒、日记

## 注意事项

1. 微信和 QQ 的自动化操作基于 UI 模拟，请确保桌面版已登录。
2. 自动回复关键词可在 `config.py` 中自定义。
3. `config.py` 中的 API Key 请勿提交到公开仓库。
4. Windows 系统下运行效果最佳。

## License

MIT
