"""
助手主控模块 - 调度语音、大脑、事务、记忆、字幕等子系统
"""

import sys
import time
import threading
import queue
import webbrowser

import config
from core.voice import VoiceEngine
from core.brain import Brain
from core.tasks import TaskHandler
from core.memory import Memory
from core.subtitle import SubtitleServer


class Assistant:
    """李亦禾助手核心调度器"""

    def __init__(self, enable_subtitle=True, enable_wechat=False):
        print("正在唤醒李亦禾...")
        self.memory = Memory()
        self.brain = Brain()
        self.tasks = TaskHandler(self.memory)
        self.voice: VoiceEngine | None = None

        self.running = False
        self._reminder_thread: threading.Thread | None = None

        self.subtitle: SubtitleServer | None = None
        self.mobile_queue: queue.Queue = queue.Queue()
        self.wechat_bot = None

        if enable_subtitle and config.WEB_ENABLED:
            self.subtitle = SubtitleServer(on_message=self._on_mobile_message)
            self.subtitle.start()
            if config.WEB_AUTO_OPEN_SUBTITLE:
                try:
                    webbrowser.open(f"http://127.0.0.1:{config.WEB_PORT}/subtitle")
                except Exception:
                    pass

        if enable_wechat:
            from platforms.wechat import WeChatBot
            self.wechat_bot = WeChatBot(self.brain, self.memory, self.subtitle)
            if self.subtitle:
                self.subtitle.set_wechat_bot(self.wechat_bot)

    def _on_mobile_message(self, text: str):
        """手机/网页发来消息时的回调"""
        self.mobile_queue.put(text)

    def _ensure_voice(self):
        if self.voice is None:
            self.voice = VoiceEngine()

    def run_voice_mode(self):
        """语音交互主循环"""
        self._ensure_voice()
        self.running = True
        greeting = f"你好主人，我是{config.ASSISTANT_NAME}，随时候命。有什么我能帮忙的吗？"
        self.voice.speak(greeting)
        if self.subtitle:
            self.subtitle.push_assistant(greeting)

        self._start_reminder_loop()

        while self.running:
            try:
                user_input = self.voice.listen(timeout=None, phrase_limit=15)
                if not user_input:
                    continue
                print(f"你: {user_input}")
                if self.subtitle:
                    self.subtitle.push_user(user_input)
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
        if self.subtitle:
            self.subtitle.push_assistant(greeting)

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
                if self.subtitle:
                    self.subtitle.push_user(user_input)
                self._process_input(user_input, source="text")
            except KeyboardInterrupt:
                self.shutdown()
                break

    def run_web_mode(self):
        """Web 模式：手机控制 + 桌面字幕，无需麦克风"""
        self.running = True
        greeting = f"你好主人，我是{config.ASSISTANT_NAME}，随时候命。有什么我能帮忙的吗？"
        print(f"李亦禾: {greeting}")
        self.memory.save_conversation("assistant", greeting, source="web")
        if self.subtitle:
            self.subtitle.push_assistant(greeting)

        self._start_reminder_loop()
        print("等待手机/网页消息中...（Ctrl+C 退出）")

        while self.running:
            try:
                user_input = self.mobile_queue.get(timeout=1)
                if not user_input:
                    continue
                if user_input in ("退出", "quit", "exit", "再见"):
                    reply = "好的主人，我去休息了。"
                    self._say(reply, "web")
                    self.shutdown()
                    break
                self._process_input(user_input, source="web")
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                self.shutdown()
                break

    def run_wechat_web_mode(self):
        """微信 + Web 联动模式：手机控制 + 微信监听 + 桌面字幕"""
        self.running = True
        greeting = f"你好主人，我是{config.ASSISTANT_NAME}，微信监听已就绪。"
        print(f"李亦禾: {greeting}")
        self.memory.save_conversation("assistant", greeting, source="web")
        if self.subtitle:
            self.subtitle.push_assistant(greeting)

        # Start WeChat listener in background thread
        if self.wechat_bot:
            wechat_thread = threading.Thread(target=self.wechat_bot.start_listening, daemon=True)
            wechat_thread.start()
            if self.subtitle:
                self.subtitle.push_status("微信监听线程已启动")

        self._start_reminder_loop()
        print("等待手机/网页消息中...（Ctrl+C 退出）")

        while self.running:
            try:
                user_input = self.mobile_queue.get(timeout=1)
                if not user_input:
                    continue
                if user_input in ("退出", "quit", "exit", "再见"):
                    reply = "好的主人，我去休息了。"
                    self._say(reply, "web")
                    self.shutdown()
                    break
                self._process_input(user_input, source="web")
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                self.shutdown()
                break

    def run_wechat_only(self):
        """仅启动微信监听模式"""
        from platforms.wechat import WeChatBot
        print("启动微信消息监听模式...")
        bot = self.wechat_bot or WeChatBot(self.brain, self.memory, self.subtitle)
        if self.subtitle and not self.subtitle.wechat_bot:
            self.subtitle.set_wechat_bot(bot)
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

        if self.subtitle:
            self.subtitle.push_status("思考中...")

        reply = self.tasks.try_handle(text)
        if reply is None:
            reply = self.brain.chat(text)

        self.memory.save_conversation("assistant", reply, source=source)
        self._say(reply, source)

    def _say(self, text: str, source: str):
        print(f"李亦禾: {text}")
        if source == "voice" and self.voice:
            self.voice.speak(text)
        if self.subtitle:
            self.subtitle.push_assistant(text)

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
        if self.wechat_bot:
            self.wechat_bot.stop()
        if self.subtitle:
            self.subtitle.push_status("李亦禾已休眠")
            self.subtitle.stop()
        if self.voice:
            self.voice.shutdown()
        self.memory.close()
        print("李亦禾已休眠。")
