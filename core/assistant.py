"""
助手主控模块 - 调度语音、大脑、事务、记忆等子系统
"""

import sys
import time
import threading

import config
from core.voice import VoiceEngine
from core.brain import Brain
from core.tasks import TaskHandler
from core.memory import Memory


class Assistant:
    """李亦禾助手核心调度器"""

    def __init__(self):
        print("正在唤醒李亦禾...")
        self.memory = Memory()
        self.brain = Brain()
        self.tasks = TaskHandler(self.memory)
        self.voice: VoiceEngine | None = None

        self.running = False
        self._reminder_thread: threading.Thread | None = None

    def _ensure_voice(self):
        if self.voice is None:
            self.voice = VoiceEngine()

    def run_voice_mode(self):
        """语音交互主循环"""
        self._ensure_voice()
        self.running = True
        self.voice.speak(f"你好主人，我是{config.ASSISTANT_NAME}，随时候命。有什么我能帮忙的吗？")

        self._start_reminder_loop()

        while self.running:
            try:
                user_input = self.voice.listen(timeout=None, phrase_limit=15)
                if not user_input:
                    continue
                print(f"你: {user_input}")
                self._process_input(user_input, source="voice")
            except KeyboardInterrupt:
                self.shutdown()
            except Exception as e:
                print(f"[错误] {e}")

    def run_text_mode(self):
        """文本交互主循环（无麦克风）"""
        self.running = True
        greeting = f"你好主人，我是{config.ASSISTANT_NAME}，随时候命。有什么我能帮忙的吗？"
        print(f"李亦禾: {greeting}")
        self.memory.save_conversation("assistant", greeting, source="text")

        self._start_reminder_loop()

        while self.running:
            try:
                user_input = input("你: ").strip()
                if not user_input:
                    continue
                if user_input in ("退出", "quit", "exit", "再见"):
                    self.voice and self.voice.speak("主人再见，随时叫我。")
                    self.shutdown()
                    break
                self._process_input(user_input, source="text")
            except KeyboardInterrupt:
                self.shutdown()
                break

    def run_wechat_only(self):
        """仅启动微信监听模式"""
        from platforms.wechat import WeChatBot

        print("启动微信消息监听模式...")
        bot = WeChatBot(self.brain, self.memory)
        bot.start_listening()

    def run_qq_only(self):
        """仅启动QQ监听模式"""
        from platforms.qq import QQBot

        print("启动QQ消息监听模式...")
        bot = QQBot(self.brain, self.memory)
        bot.start_listening()

    def _process_input(self, text: str, source: str = "voice"):
        """处理用户输入：先匹配指令，再交给大脑对话"""
        self.memory.save_conversation("user", text, source=source)

        if text in ("退出", "quit", "exit", "再见", "关机"):
            reply = "好的主人，我去休息了，随时叫我。"
            self.memory.save_conversation("assistant", reply, source=source)
            self._say(reply, source)
            self.shutdown()
            return

        reply = self.tasks.try_handle(text)
        if reply is None:
            reply = self.brain.chat(text)

        self.memory.save_conversation("assistant", reply, source=source)
        self._say(reply, source)

    def _say(self, text: str, source: str):
        print(f"李亦禾: {text}")
        if source == "voice" and self.voice:
            self.voice.speak(text)

    def _start_reminder_loop(self):
        def loop():
            while self.running:
                reminder = self.tasks.check_reminders()
                if reminder:
                    print(f"[提醒] {reminder}")
                    self._say(reminder, "voice" if self.voice else "text")
                time.sleep(config.REMINDER_CHECK_INTERVAL)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def shutdown(self):
        self.running = False
        if self.voice:
            self.voice.shutdown()
        self.memory.close()
        print("李亦禾已休眠。")
