"""
QQ 自动化模块 - 通过 UI 自动化监听和回复 QQ 消息

原理与微信模块类似，通过 uiautomation / pyautogui 操作 QQ 桌面版。
"""

import time
import threading
import subprocess

import config

try:
    import pyautogui
    import pyperclip
except ImportError:
    pyautogui = None
    pyperclip = None

try:
    import uiautomation as uia
except ImportError:
    uia = None


class QQBot:
    """QQ 消息自动化处理"""

    def __init__(self, brain, memory):
        self.brain = brain
        self.memory = memory
        self.running = False
        self._checked_messages: set = set()

    def ensure_qq_open(self):
        """确保 QQ 已打开"""
        try:
            subprocess.Popen(["start", "QQ"], shell=True)
            time.sleep(3)
        except Exception:
            pass

    def start_listening(self):
        """启动消息监听循环"""
        self.ensure_qq_open()
        self.running = True
        print("QQ 监听已启动，等待消息中...")

        if uia:
            self._listen_with_uia()
        elif pyautogui:
            self._listen_with_pyautogui()
        else:
            print("需要安装 pyautogui 或 uiautomation: pip install pyautogui uiautomation")

    def _listen_with_uia(self):
        """使用 uiautomation 监听 QQ 消息"""
        while self.running:
            try:
                qq = uia.WindowControl(Name="QQ", ClassName="TXGuiFoundation")
                if not qq.Exists():
                    print("未检测到QQ窗口，请确保已登录QQ桌面版。")
                    time.sleep(10)
                    continue

                qq.SetTopmost(True)
                time.sleep(0.5)
                qq.SetTopmost(False)

                chat_list = qq.ListControl(foundIndex=1)
                if not chat_list.Exists():
                    time.sleep(5)
                    continue

                for item in chat_list.GetChildren():
                    try:
                        name = item.Name
                        if not name:
                            continue

                        text_items = item.GetChildren()
                        last_msg = ""
                        for ti in text_items:
                            if ti.ControlType == uia.ControlType.TextControl and ti.Name:
                                last_msg = ti.Name

                        if not last_msg:
                            continue

                        msg_key = f"{name}:{last_msg}"
                        if msg_key in self._checked_messages:
                            continue
                        self._checked_messages.add(msg_key)

                        if len(self._checked_messages) > 200:
                            self._checked_messages = set(list(self._checked_messages)[-100:])

                        if not self._should_reply(last_msg):
                            continue

                        print(f"[QQ] {name}: {last_msg}")
                        self._reply_to_contact(qq, name, last_msg)
                    except Exception:
                        continue

                time.sleep(3)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"[QQ监听错误] {e}")
                time.sleep(5)

    def _listen_with_pyautogui(self):
        """简化监听方案"""
        print("使用 pyautogui 模式（简化版），建议安装 uiautomation。")
        print("按 Ctrl+C 退出。")
        while self.running:
            try:
                input("按回车处理QQ消息（或 Ctrl+C 退出）...")
                msg = input("输入收到的消息: ").strip()
                if msg:
                    reply = self.brain.generate_reply("QQ好友", msg)
                    print(f"建议回复: {reply}")
                    pyperclip.copy(reply)
                    print("回复已复制到剪贴板。")
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"[QQ错误] {e}")

    def _should_reply(self, message: str) -> bool:
        if not config.QQ_AUTO_REPLY_ENABLED:
            return False
        for kw in config.WECHAT_REPLY_KEYWORDS:
            if kw in message:
                return True
        return False

    def _reply_to_contact(self, qq_window, name: str, message: str):
        """点击联系人并回复消息"""
        try:
            qq_window.SetTopmost(True)
            time.sleep(0.3)

            reply = self.brain.generate_reply(name, message)
            print(f"[回复] -> {name}: {reply}")

            self.memory.save_contact(name, "qq", message)
            self.memory.save_conversation("user", f"[QQ-{name}] {message}", source="qq")
            self.memory.save_conversation("assistant", reply, source="qq")

            if pyperclip and pyautogui:
                pyperclip.copy(reply)
                time.sleep(0.2)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.3)
                pyautogui.press("enter")

            qq_window.SetTopmost(False)
        except Exception as e:
            print(f"[回复失败] {e}")

    def stop(self):
        self.running = False
