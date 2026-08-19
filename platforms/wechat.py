"""
微信自动化模块 - 通过 UI 自动化监听和回复微信消息

功能：
  1. 桌面端：自动监听微信消息，AI 自动回复
  2. 手机端：通过 Web 服务器推送新消息到手机，手机可查看和手动回复

注意：需要先在电脑上登录微信桌面版。
"""

import time
import threading
import subprocess
import os
import queue

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
    """微信消息自动化处理 - 桌面 + 手机联动"""

    def __init__(self, brain, memory, subtitle_server=None):
        self.brain = brain
        self.memory = memory
        self.subtitle = subtitle_server
        self.running = False
        self._checked_messages: set = set()
        self.auto_reply = config.WECHAT_AUTO_REPLY_ENABLED
        self.wechat_messages: list[dict] = []  # 微信消息列表
        self.max_messages = 100
        self._send_queue: queue.Queue = queue.Queue()  # 手机发来的待发送消息

    def push_wechat_msg(self, contact: str, message: str, direction: str = "in"):
        """推送微信消息到手机和本地列表"""
        msg = {
            "contact": contact,
            "message": message,
            "direction": direction,
            "timestamp": time.strftime("%H:%M:%S"),
        }
        self.wechat_messages.append(msg)
        if len(self.wechat_messages) > self.max_messages:
            self.wechat_messages = self.wechat_messages[-self.max_messages:]

        if self.subtitle:
            if direction == "in":
                self.subtitle.push("wechat", f"[微信] {contact}: {message}")
            else:
                self.subtitle.push("wechat", f"[回复] -> {contact}: {message}")

    def get_messages(self) -> list[dict]:
        """获取微信消息列表"""
        return self.wechat_messages

    def queue_send(self, contact: str, message: str):
        """手机请求发送微信消息（加入队列，由桌面端执行）"""
        self._send_queue.put((contact, message))

    def toggle_auto_reply(self, enabled: bool = None):
        """开关自动回复"""
        if enabled is not None:
            self.auto_reply = enabled
        else:
            self.auto_reply = not self.auto_reply
        return self.auto_reply

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

        if self.subtitle:
            self.subtitle.push_status("微信监听已启动")

        # Start send queue processor thread
        send_thread = threading.Thread(target=self._process_send_queue, daemon=True)
        send_thread.start()

        if uia:
            self._listen_with_uia()
        elif pyautogui:
            self._listen_with_pyautogui()
        else:
            print("需要安装 pyautogui 或 uiautomation: pip install pyautogui uiautomation")
            if self.subtitle:
                self.subtitle.push_status("微信模块需要 pyautogui/uiautomation")

    def _process_send_queue(self):
        """处理手机发来的待发送消息"""
        while self.running:
            try:
                contact, message = self._send_queue.get(timeout=1)
                self._send_message_to_contact(contact, message)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[发送队列错误] {e}")

    def _listen_with_uia(self):
        """使用 uiautomation 库监听微信消息"""
        while self.running:
            try:
                wechat = uia.WindowControl(Name="微信", ClassName="WeChatMainWndForPC")
                if not wechat.Exists():
                    print("未检测到微信窗口，请确保已登录微信桌面版。")
                    if self.subtitle:
                        self.subtitle.push_status("未检测到微信窗口，请登录微信桌面版")
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

                        # Push to mobile
                        self.push_wechat_msg(name, last_msg, "in")

                        if self.auto_reply and self._should_reply(last_msg):
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
        while self.running:
            try:
                time.sleep(5)
                if not self._send_queue.empty():
                    contact, message = self._send_queue.get_nowait()
                    print(f"[待发送] {contact}: {message}")
                    print("请在微信中手动粘贴发送。")
                    if pyperclip:
                        pyperclip.copy(message)
                    self.push_wechat_msg(contact, message, "out")
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"[微信错误] {e}")

    def _should_reply(self, message: str) -> bool:
        """判断是否应该自动回复"""
        if not self.auto_reply:
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
            print(f"[自动回复] -> {name}: {reply}")
            self.push_wechat_msg(name, reply, "out")

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
            if self.subtitle:
                self.subtitle.push_status(f"微信回复失败: {e}")

    def _send_message_to_contact(self, contact: str, message: str):
        """通过微信桌面版发送消息给指定联系人"""
        if not uia:
            print(f"[发送] 需要uiautomation: {contact}: {message}")
            if pyperclip:
                pyperclip.copy(message)
            self.push_wechat_msg(contact, message, "out")
            return

        try:
            wechat = uia.WindowControl(Name="微信", ClassName="WeChatMainWndForPC")
            if not wechat.Exists():
                print("未检测到微信窗口")
                if self.subtitle:
                    self.subtitle.push_status("未检测到微信窗口")
                return

            wechat.SetTopmost(True)
            time.sleep(0.3)

            search_box = wechat.EditControl(Name="搜索")
            if search_box.Exists():
                search_box.Click()
                time.sleep(0.3)
                pyperclip.copy(contact)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(1)

            edit_box = wechat.EditControl(Name="输入信息")
            if edit_box.Exists():
                edit_box.Click()
                time.sleep(0.3)
                pyperclip.copy(message)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.3)
                pyautogui.press("enter")
                print(f"[已发送] -> {contact}: {message}")
                self.push_wechat_msg(contact, message, "out")
            else:
                print(f"[发送失败] 未找到输入框")
                if self.subtitle:
                    self.subtitle.push_status(f"发送给{contact}失败")

            wechat.SetTopmost(False)
        except Exception as e:
            print(f"[发送错误] {e}")
            if self.subtitle:
                self.subtitle.push_status(f"发送错误: {e}")

    def stop(self):
        self.running = False
