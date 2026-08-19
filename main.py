#!/usr/bin/env python3
"""
李亦禾 AI 助手 - 主入口
======================
启动后，李亦禾将持续监听你的语音指令。
说「李亦禾」唤醒，然后说出你的需求。

功能概览：
  - 语音控制：唤醒词识别 + 自然语言指令
  - 事务处理：天气查询、时间提醒、打开应用、网页搜索等
  - 消息回复：自动处理微信和 QQ 消息
  - 情感陪伴：基于大模型的对话和情绪关怀
  - 生活记录：对话日志、日记、备忘录
  - 屏幕字幕：桌面底部实时字幕浮窗
  - 手机控制：手机浏览器访问，查看字幕 + 发送指令
  - 微信接入：在微信文件传输助手中直接与李亦禾对话

用法：
    python main.py                  # 语音模式（自动开启字幕+手机）
    python main.py --text           # 文本模式（无麦克风，自动开启字幕+手机）
    python main.py --web            # Web 模式（手机/网页控制 + 桌面字幕）
    python main.py --wechat         # 微信聊天模式（在文件传输助手中对话）
    python main.py --wechat-reply   # 微信自动回复模式（关键词触发回复）
    python main.py --qq             # QQ监听模式
    python main.py --no-subtitle    # 禁用字幕浮窗和手机控制
"""

import sys
import argparse

from core.assistant import Assistant


def main():
    parser = argparse.ArgumentParser(description="李亦禾 AI 助手 - 你的私人 JARVIS")
    parser.add_argument("--text", action="store_true", help="文本交互模式（不用麦克风）")
    parser.add_argument("--web", action="store_true", help="Web 模式（手机/网页控制 + 桌面字幕）")
    parser.add_argument("--wechat", action="store_true", help="微信聊天模式（在文件传输助手中对话）")
    parser.add_argument("--wechat-reply", action="store_true", help="微信自动回复模式（关键词触发）")
    parser.add_argument("--qq", action="store_true", help="QQ消息监听")
    parser.add_argument("--no-subtitle", action="store_true", help="禁用字幕浮窗和手机控制")
    args = parser.parse_args()

    enable_subtitle = not args.no_subtitle
    assistant = Assistant(enable_subtitle=enable_subtitle)

    if args.wechat:
        assistant.run_wechat_only(chat_mode=True)
    elif args.wechat_reply:
        assistant.run_wechat_only(chat_mode=False)
    elif args.qq:
        assistant.run_qq_only()
    elif args.web:
        assistant.run_web_mode()
    elif args.text:
        assistant.run_text_mode()
    else:
        assistant.run_voice_mode()


if __name__ == "__main__":
    main()
