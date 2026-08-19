"""
微信自动化模块 - 控件级后台操作

核心原理：
  - 消息读取: uiautomation 读聊天列表，完全后台，不抢焦点
  - 打开聊天: search.Click() + search.SendKeys() 是控件级操作，不抢焦点
  - 发送消息: 获取输入框焦点控件→发送→立即恢复之前前台窗口
    (只有一瞬间闪烁，不会持续占用界面)

注意：微信窗口需要保持打开（可以在其他窗口后面），不需要最小化。
"""

import time
import threading
import subprocess
import os
import ctypes

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

if pyautogui:
    pyautogui.FAILSAFE = False

user32 = ctypes.windll.user32


class WeChatInterface:
    """微信交互接口 - 控件级后台操作"""

    def __init__(self, assistant, chat_mode=True):
        self.assistant = assistant
        self.chat_mode = chat_mode
        self.running = False
        self.target_chat = config.WECHAT_CHAT_TARGET
        self._wechat_window = None
        self._hwnd = 0
        self._last_msg_text = ""
        self._pending_reply = ""
        self._checked_messages: set = set()

    def start(self):
        self._ensure_wechat_open()
        if self.chat_mode:
            self._start_chat_mode()
        else:
            self._start_auto_reply_mode()

    # ==================== 窗口管理 ====================

    def _ensure_wechat_open(self):
        print("[微信] 正在检测微信桌面版...", flush=True)

        if uia:
            wechat = uia.WindowControl(ClassName="WeChatMainWndForPC")
            if wechat.Exists(2, 1):
                self._wechat_window = wechat
                self._hwnd = wechat.NativeWindowHandle
                print("[微信] 已检测到微信窗口", flush=True)
                self._ensure_visible()
                return

        print("[微信] 未检测到微信，尝试启动...", flush=True)
        try:
            wechat_path = config.WECHAT_APP_PATH
            if os.path.exists(wechat_path):
                subprocess.Popen([wechat_path])
            else:
                subprocess.Popen("start WeChat", shell=True)
            time.sleep(5)

            if uia:
                wechat = uia.WindowControl(ClassName="WeChatMainWndForPC")
                if wechat.Exists(3, 1):
                    self._wechat_window = wechat
                    self._hwnd = wechat.NativeWindowHandle
                    print("[微信] 微信已启动", flush=True)
                    self._ensure_visible()
                    return
        except Exception as e:
            print(f"[微信] 启动失败: {e}", flush=True)

        print("[微信] 请手动打开并登录微信桌面版。", flush=True)

    def _ensure_visible(self):
        """确保微信窗口可见（非最小化）"""
        if not self._wechat_window:
            return

        rect = self._wechat_window.BoundingRectangle
        if rect.right - rect.left > 100:
            return  # 已可见

        print("[微信] 窗口最小化，恢复中...", flush=True)
        SW_RESTORE = 9
        if self._hwnd:
            user32.keybd_event(0x12, 0, 0, 0)
            user32.keybd_event(0x12, 0, 0x2, 0)
            user32.ShowWindow(self._hwnd, SW_RESTORE)
            time.sleep(1)
            user32.SetForegroundWindow(self._hwnd)
            time.sleep(1)

        rect = self._wechat_window.BoundingRectangle
        if rect.right - rect.left < 100:
            try:
                subprocess.Popen([config.WECHAT_APP_PATH])
                time.sleep(3)
            except Exception:
                pass

        rect = self._wechat_window.BoundingRectangle
        if rect.right - rect.left < 100:
            try:
                WM_SYSCOMMAND = 0x0112
                SC_RESTORE = 0xF120
                user32.SendMessageW(self._hwnd, WM_SYSCOMMAND, SC_RESTORE, 0)
                time.sleep(1)
            except Exception:
                pass

    def _is_visible(self) -> bool:
        if not self._wechat_window:
            return False
        r = self._wechat_window.BoundingRectangle
        return r.right - r.left > 100

    # ==================== 聊天模式 ====================

    def _start_chat_mode(self):
        if not uia or not pyautogui:
            print("[微信] 需要 uiautomation 和 pyautogui", flush=True)
            return

        self._open_target_chat()

        self.running = True
        greeting = f"你好主人，我是{config.ASSISTANT_NAME}，微信已连接。"
        self._send_message(greeting)
        self.assistant.memory.save_conversation("assistant", greeting, source="wechat")
        if self.assistant.subtitle:
            self.assistant.subtitle.push_assistant(greeting)

        print(f"\n[微信] 李亦禾已接入微信（{self.target_chat}）", flush=True)
        print("[微信] 在微信中发消息即可对话", flush=True)
        print("[微信] 按 Ctrl+C 退出\n", flush=True)

        self._start_reminder_forward()

        loop_count = 0
        while self.running:
            try:
                loop_count += 1

                new_msg = self._check_new_message()
                if new_msg:
                    self._process_chat_message(new_msg)

                # 每 30 秒检查窗口是否可见
                if loop_count % 15 == 0 and not self._is_visible():
                    self._ensure_visible()

                time.sleep(2)
            except KeyboardInterrupt:
                farewell = "主人，我要先休息了。微信随时找我哦~"
                self._send_message(farewell)
                self.running = False
            except Exception as e:
                print(f"[微信监听错误] {e}", flush=True)
                try:
                    self._ensure_wechat_open()
                except Exception:
                    pass
                time.sleep(5)

    def _open_target_chat(self) -> bool:
        """用 uiautomation 控件级操作打开聊天（后台，不抢焦点）"""
        try:
            search = self._wechat_window.EditControl(Name="搜索")
            if not search.Exists(2, 0.5):
                print("[微信] 未找到搜索框", flush=True)
                return False

            # 控件级操作: Click + SendKeys 都不需要窗口在前台
            search.Click()
            time.sleep(0.3)
            search.SendKeys("{Ctrl}a{Delete}", waitTime=0.1)
            pyperclip.copy(self.target_chat)
            search.SendKeys("{Ctrl}v", waitTime=2)
            search.SendKeys("{Enter}", waitTime=2)

            print(f"[微信] 已打开聊天: {self.target_chat}", flush=True)
            self._last_msg_text = self._read_last_message()
            return True
        except Exception as e:
            print(f"[微信] 打开聊天失败: {e}", flush=True)
            return False

    def _read_last_message(self) -> str:
        """读取聊天列表中目标聊天的最后消息预览（完全后台）"""
        try:
            list_ctrl = self._wechat_window.ListControl(Name="会话")
            if not list_ctrl.Exists(0.5):
                return ""

            for item in list_ctrl.GetChildren():
                name = item.Name
                if not name or self.target_chat not in name:
                    continue
                msg_item = item.TextControl(foundIndex=3)
                if msg_item.Exists(0.3):
                    return msg_item.Name
            return ""
        except Exception:
            return ""

    def _check_new_message(self) -> str | None:
        try:
            current = self._read_last_message()
            if not current or current == self._last_msg_text:
                return None
            if current == self._pending_reply:
                self._last_msg_text = current
                self._pending_reply = ""
                return None
            self._last_msg_text = current
            return current
        except Exception:
            return None

    def _process_chat_message(self, text: str):
        print(f"[微信] 你: {text}", flush=True)
        if self.assistant.subtitle:
            self.assistant.subtitle.push_user(text)

        self.assistant.memory.save_conversation("user", text, source="wechat")

        if text in ("退出", "quit", "exit", "再见"):
            reply = "好的主人，我去休息了，微信随时找我哦~"
            self._send_and_record(reply)
            self.running = False
            return

        if self.assistant.subtitle:
            self.assistant.subtitle.push_status("思考中...")

        reply = self.assistant.tasks.try_handle(text)
        if reply is None:
            reply = self.assistant.brain.chat(text)

        self._send_and_record(reply)

    def _send_and_record(self, reply: str):
        self.assistant.memory.save_conversation("assistant", reply, source="wechat")
        if self.assistant.subtitle:
            self.assistant.subtitle.push_assistant(reply)
        print(f"[微信] 李亦禾: {reply}", flush=True)
        self._send_message(reply)

    def _send_message(self, text: str):
        """发送消息: 保存前台→打开聊天→获取输入框→发送→恢复前台"""
        if not self._wechat_window:
            return
        try:
            # 1. 保存当前前台窗口
            prev_fg = user32.GetForegroundWindow()

            # 2. 确保窗口可见
            if not self._is_visible():
                self._ensure_visible()

            # 3. 用控件级操作打开聊天 (不抢焦点)
            search = self._wechat_window.EditControl(Name="搜索")
            if search.Exists(1, 0.5):
                search.Click()
                time.sleep(0.3)
                search.SendKeys("{Ctrl}a{Delete}", waitTime=0.1)
                pyperclip.copy(self.target_chat)
                search.SendKeys("{Ctrl}v", waitTime=1.5)
                search.SendKeys("{Enter}", waitTime=1.5)

            # 4. 获取输入框焦点控件
            input_box = uia.GetFocusedControl()
            if not input_box:
                print("[微信] 无法获取输入框", flush=True)
                return

            # 5. 发送消息 (CustomControl.SendKeys 会短暂抢焦点)
            input_box.SendKeys("{Ctrl}a{Delete}", waitTime=0.1)
            pyperclip.copy(text)
            input_box.SendKeys("{Ctrl}v", waitTime=0.3)
            input_box.SendKeys("{Enter}", waitTime=0.5)
            self._pending_reply = text

            # 6. 立即恢复之前的前台窗口
            time.sleep(0.1)
            if prev_fg and prev_fg != self._hwnd:
                user32.SetForegroundWindow(prev_fg)

            print("[微信] 消息已发送", flush=True)
        except Exception as e:
            print(f"[微信] 发送失败: {e}", flush=True)
            # 恢复前台
            try:
                if prev_fg and prev_fg != self._hwnd:
                    user32.SetForegroundWindow(prev_fg)
            except Exception:
                pass

    def _start_reminder_forward(self):
        def loop():
            while self.running:
                try:
                    reminder = self.assistant.tasks.check_reminders()
                    if reminder:
                        print(f"[提醒] {reminder}", flush=True)
                        self._send_message(reminder)
                        if self.assistant.subtitle:
                            self.assistant.subtitle.push_assistant(f"[提醒] {reminder}")
                    time.sleep(config.REMINDER_CHECK_INTERVAL)
                except Exception:
                    pass

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    # ==================== 自动回复模式 ====================

    def _start_auto_reply_mode(self):
        self.running = True
        print("[微信] 自动回复模式已启动", flush=True)
        print("[微信] 按 Ctrl+C 退出", flush=True)

        while self.running:
            try:
                list_ctrl = self._wechat_window.ListControl(Name="会话")
                if not list_ctrl.Exists(0.5):
                    time.sleep(5)
                    continue

                for item in list_ctrl.GetChildren():
                    try:
                        name = item.Name
                        if not name or self.target_chat in name:
                            continue
                        name = name.replace("已置顶", "").strip()

                        msg_item = item.TextControl(foundIndex=3)
                        if not msg_item.Exists(0.3):
                            continue
                        last_msg = msg_item.Name
                        if not last_msg or last_msg == "[未读消息]":
                            continue

                        msg_key = f"{name}:{last_msg}"
                        if msg_key in self._checked_messages:
                            continue
                        self._checked_messages.add(msg_key)
                        if len(self._checked_messages) > 200:
                            self._checked_messages = set(
                                list(self._checked_messages)[-100:]
                            )

                        if not self._should_reply(last_msg):
                            continue

                        print(f"[微信] {name}: {last_msg}", flush=True)
                        self._reply_to_contact(name, last_msg)
                    except Exception:
                        continue

                time.sleep(3)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"[微信监听错误] {e}", flush=True)
                time.sleep(5)

    def _should_reply(self, message: str) -> bool:
        if not config.WECHAT_AUTO_REPLY_ENABLED:
            return False
        for kw in config.WECHAT_REPLY_KEYWORDS:
            if kw in message:
                return True
        return False

    def _reply_to_contact(self, name: str, message: str):
        try:
            prev_fg = user32.GetForegroundWindow()

            search = self._wechat_window.EditControl(Name="搜索")
            if search.Exists(1, 0.5):
                search.Click()
                time.sleep(0.3)
                search.SendKeys("{Ctrl}a{Delete}", waitTime=0.1)
                pyperclip.copy(name)
                search.SendKeys("{Ctrl}v", waitTime=1.5)
                search.SendKeys("{Enter}", waitTime=2)

            reply = self.assistant.brain.generate_reply(name, message)
            print(f"[回复] -> {name}: {reply}", flush=True)

            self.assistant.memory.save_contact(name, "wechat", message)
            self.assistant.memory.save_conversation("user", f"[微信-{name}] {message}", source="wechat")
            self.assistant.memory.save_conversation("assistant", reply, source="wechat")

            if self.assistant.subtitle:
                self.assistant.subtitle.push_user(f"[{name}] {message}")
                self.assistant.subtitle.push_assistant(reply)

            input_box = uia.GetFocusedControl()
            if input_box:
                input_box.SendKeys("{Ctrl}a{Delete}", waitTime=0.1)
                pyperclip.copy(reply)
                input_box.SendKeys("{Ctrl}v", waitTime=0.3)
                input_box.SendKeys("{Enter}", waitTime=0.5)

            time.sleep(0.1)
            if prev_fg and prev_fg != self._hwnd:
                user32.SetForegroundWindow(prev_fg)
        except Exception as e:
            print(f"[回复失败] {e}", flush=True)

    def stop(self):
        self.running = False
