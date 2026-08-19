"""
微信自动化模块 - 通过 UI 自动化监听和回复微信消息

原理：
  使用 pyautogui / uiautomation 模拟操作微信桌面版，
  定时检测新消息并自动回复。

注意：
  需要先在电脑上登录微信桌面版。
  微信没有开放 API，此方案通过 UI 自动化实现。
"""

import time
import threading
import subprocess
import os

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


class WeChatBot:
    """微信消息自动化处理"""

    def __init__(self, brain, memory):
        self.brain = brain
        self.memory = memory
        self.running = False
        self._checked_messages: set = set()

    def ensure_wechat_open(self):
        """确保微信已打开"""
        try:
            subprocess.Popen(["start", "WeChat"], shell=True)
            time.sleep(3)
        except Exception:
            pass

    def start_listening(self):
        """启动消息监听循环"""
        self.ensure_wechat_open()
        self.running = True
        print("微信监听已启动，等待消息中...")

        if uia:
            self._listen_with_uia()
        elif pyautogui:
            self._listen_with_pyautogui()
        else:
            print("需要安装 pyautogui 或 uiautomation: pip install pyautogui uiautomation")

    def _listen_with_uia(self):
        """使用 uiautomation 库监听微信消息"""
        while self.running:
            try:
                wechat = uia.WindowControl(Name="微信", ClassName="WeChatMainWndForPC")
                if not wechat.Exists():
                    print("未检测到微信窗口，请确保已登录微信桌面版。")
                    time.sleep(10)
                    continue

                wechat.SetTopmost(True)
                time.sleep(0.5)
                wechat.SetTopmost(False)

                list_ctrl = wechat.ListControl(Name="会话")
                if not list_ctrl.Exists():
                    time.sleep(5)
                    continue

                for item in list_ctrl.GetChildren():
                    try:
                        name = item.Name
                        if not name:
                            continue

                        last_msg = ""
                        msg_item = item.TextControl(foundIndex=2)
                        if msg_item.Exists():
                            last_msg = msg_item.Name

                        if not last_msg or last_msg == "[未读消息]":
                            continue

                        msg_key = f"{name}:{last_msg}"
                        if msg_key in self._checked_messages:
                            continue
                        self._checked_messages.add(msg_key)

                        if len(self._checked_messages) > 200:
                            self._checked_messages = set(list(self._checked_messages)[-100:])

                        if not self._should_reply(last_msg):
                            continue

                        print(f"[微信] {name}: {last_msg}")
                        self._reply_to_contact(wechat, name, last_msg)
                    except Exception:
                        continue

                time.sleep(3)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"[微信监听错误] {e}")
                time.sleep(5)

    def _listen_with_pyautogui(self):
        """使用 pyautogui 的简化监听方案"""
        print("使用 pyautogui 模式（简化版），建议安装 uiautomation 以获得更好体验。")
        print("按 Ctrl+C 退出。")
        while self.running:
            try:
                input("按回车处理微信消息（或 Ctrl+C 退出）...")
                if pyautogui:
                    pyautogui.hotkey("ctrl", "alt", "w")
                    time.sleep(1)
                    pyautogui.hotkey("ctrl", "f")
                    time.sleep(0.5)
                    print("请在微信中选择聊天，然后回到终端按回车...")
                    input("准备好后按回车...")
                    msg = input("输入收到的消息: ").strip()
                    if msg:
                        reply = self.brain.generate_reply("微信好友", msg)
                        print(f"建议回复: {reply}")
                        pyperclip.copy(reply)
                        print("回复已复制到剪贴板，粘贴到微信发送即可。")
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"[微信错误] {e}")

    def _should_reply(self, message: str) -> bool:
        """判断是否应该自动回复"""
        if not config.WECHAT_AUTO_REPLY_ENABLED:
            return False
        for kw in config.WECHAT_REPLY_KEYWORDS:
            if kw in message:
                return True
        return False

    def _reply_to_contact(self, wechat_window, name: str, message: str):
        """点击联系人并回复消息"""
        try:
            wechat_window.SetTopmost(True)
            time.sleep(0.3)

            search_box = wechat_window.EditControl(Name="搜索")
            if search_box.Exists():
                search_box.Click()
                time.sleep(0.3)
                pyperclip.copy(name)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(1)

            reply = self.brain.generate_reply(name, message)
            print(f"[回复] -> {name}: {reply}")

            self.memory.save_contact(name, "wechat", message)
            self.memory.save_conversation("user", f"[微信-{name}] {message}", source="wechat")
            self.memory.save_conversation("assistant", reply, source="wechat")

            edit_box = wechat_window.EditControl(Name="输入信息")
            if edit_box.Exists():
                edit_box.Click()
                time.sleep(0.3)
                pyperclip.copy(reply)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.3)
                pyautogui.press("enter")

            wechat_window.SetTopmost(False)
        except Exception as e:
            print(f"[回复失败] {e}")

    def stop(self):
        self.running = False
