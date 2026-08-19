"""
微信自动化模块 - 通过 UI 自动化将李亦禾接入微信

两种模式：
  1. 聊天模式 (chat_mode=True)
     - 用户在微信「文件传输助手」中与李亦禾对话
     - 所有消息走完整助手管线（事务指令 + LLM 对话 + 记忆）
     - 字幕浮窗和手机网页同步显示对话

  2. 自动回复模式 (chat_mode=False)
     - 监听所有联系人消息，关键词触发自动回复

注意：需要先在电脑上登录微信桌面版。
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


class WeChatInterface:
    """微信交互接口 - 让李亦禾在微信中工作"""

    def __init__(self, assistant, chat_mode=True):
        self.assistant = assistant
        self.chat_mode = chat_mode
        self.running = False
        self.target_chat = config.WECHAT_CHAT_TARGET
        self._last_msg_text = ""
        self._wechat_window = None
        self._checked_messages: set = set()

    def start(self):
        """启动微信交互"""
        self._ensure_wechat_open()

        if self.chat_mode:
            self._start_chat_mode()
        else:
            self._start_auto_reply_mode()

    def _ensure_wechat_open(self):
        """确保微信桌面版已打开并登录"""
        print("[微信] 正在检测微信桌面版...")

        if uia:
            wechat = uia.WindowControl(ClassName="WeChatMainWndForPC")
            if wechat.Exists():
                print("[微信] 已检测到微信窗口")
                wechat.SetTopmost(True)
                time.sleep(0.5)
                wechat.SetTopmost(False)
                return

        print("[微信] 未检测到微信，尝试启动...")
        try:
            wechat_path = r"C:\Program Files\Tencent\WeChat\WeChat.exe"
            if os.path.exists(wechat_path):
                subprocess.Popen([wechat_path])
            else:
                subprocess.Popen("start WeChat", shell=True)
            time.sleep(5)

            if uia:
                wechat = uia.WindowControl(ClassName="WeChatMainWndForPC")
                if wechat.Exists():
                    print("[微信] 微信已启动")
                    return
        except Exception as e:
            print(f"[微信] 启动失败: {e}")

        print("[微信] 请手动打开并登录微信桌面版，然后重试。")

    # ==================== 聊天模式 ====================

    def _start_chat_mode(self):
        """聊天模式：通过文件传输助手与李亦禾对话"""
        if not uia:
            print("[微信] 需要 uiautomation 库: pip install uiautomation")
            return

        if not self._open_target_chat():
            return

        self.running = True
        greeting = f"你好主人，我是{config.ASSISTANT_NAME}，微信已连接。有什么我能帮忙的吗？"
        self._send_message(greeting)
        self.assistant.memory.save_conversation("assistant", greeting, source="wechat")
        if self.assistant.subtitle:
            self.assistant.subtitle.push_assistant(greeting)

        print(f"\n[微信] 李亦禾已接入微信（{self.target_chat}）")
        print("[微信] 在微信中给文件传输助手发消息即可与李亦禾对话")
        print("[微信] 按 Ctrl+C 退出\n")

        self._start_reminder_forward()

        while self.running:
            try:
                new_msg = self._check_new_message()
                if new_msg:
                    self._process_chat_message(new_msg)
                time.sleep(2)
            except KeyboardInterrupt:
                farewell = "主人，我要先休息了。微信随时找我哦~"
                self._send_message(farewell)
                self.running = False
            except Exception as e:
                print(f"[微信监听错误] {e}")
                time.sleep(5)

    def _open_target_chat(self) -> bool:
        """打开目标聊天窗口（文件传输助手）"""
        try:
            wechat = uia.WindowControl(ClassName="WeChatMainWndForPC")
            if not wechat.Exists(3, 1):
                print("[微信] 未找到微信窗口")
                return False

            self._wechat_window = wechat
            wechat.SetTopmost(True)
            time.sleep(0.5)

            search_box = wechat.EditControl(Name="搜索")
            if search_box.Exists(1):
                search_box.Click()
                time.sleep(0.3)
                pyperclip.copy(self.target_chat)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.8)
                pyautogui.press("enter")
                time.sleep(1.5)
                print(f"[微信] 已打开聊天: {self.target_chat}")
            else:
                print("[微信] 未找到搜索框，请手动打开文件传输助手")
                return False

            self._last_msg_text = self._get_last_message()
            wechat.SetTopmost(False)
            return True
        except Exception as e:
            print(f"[微信] 打开聊天失败: {e}")
            return False

    def _get_last_message(self) -> str:
        """获取聊天窗口最后一条消息文本"""
        try:
            if not self._wechat_window:
                return ""

            msg_list = self._wechat_window.ListControl(Name="消息")
            if not msg_list.Exists(0.5):
                msg_list = self._wechat_window.ListControl(SubName="消息")
            if not msg_list.Exists(0.5):
                return ""

            children = msg_list.GetChildren()
            last_text = ""
            for child in children:
                texts = child.GetChildren()
                for t in texts:
                    if t.ControlType == uia.ControlType.TextControl:
                        val = t.Name
                        if val and len(val) > 1 and val != "[文件]" and val != "[图片]":
                            last_text = val

            if not last_text:
                last_msg_item = msg_list.GetChildren()[-1] if msg_list.GetChildren() else None
                if last_msg_item:
                    text_ctrl = last_msg_item.TextControl(foundIndex=1)
                    if text_ctrl.Exists(0.3):
                        last_text = text_ctrl.Name

            return last_text
        except Exception:
            return ""

    def _check_new_message(self) -> str | None:
        """检查是否有新消息（与上次不同且不是自己发的）"""
        try:
            current = self._get_last_message()
            if not current:
                return None
            if current == self._last_msg_text:
                return None
            if current == self._pending_reply:
                self._last_msg_text = current
                self._pending_reply = ""
                return None

            new_msg = current
            self._last_msg_text = current
            return new_msg
        except Exception:
            return None

    _pending_reply = ""

    def _process_chat_message(self, text: str):
        """处理微信消息：走完整助手管线"""
        print(f"[微信] 你: {text}")
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
        """发送回复并记录"""
        self.assistant.memory.save_conversation("assistant", reply, source="wechat")
        if self.assistant.subtitle:
            self.assistant.subtitle.push_assistant(reply)
        print(f"[微信] 李亦禾: {reply}")
        self._send_message(reply)

    def _send_message(self, text: str):
        """在当前聊天窗口发送消息"""
        if not self._wechat_window:
            return
        try:
            self._wechat_window.SetTopmost(True)
            time.sleep(0.2)

            edit_box = self._wechat_window.EditControl(Name="输入信息")
            if not edit_box.Exists(0.5):
                edit_box = self._wechat_window.EditControl(foundIndex=1)

            if edit_box.Exists(0.5):
                edit_box.Click()
                time.sleep(0.2)
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.3)
                pyautogui.press("enter")
                self._pending_reply = text
                time.sleep(0.5)

            self._wechat_window.SetTopmost(False)
        except Exception as e:
            print(f"[微信] 发送失败: {e}")

    def _start_reminder_forward(self):
        """启动提醒转发线程"""
        def loop():
            while self.running:
                try:
                    reminder = self.assistant.tasks.check_reminders()
                    if reminder:
                        print(f"[提醒] {reminder}")
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
        """自动回复模式：监听所有联系人，关键词触发回复"""
        self.running = True
        print("[微信] 自动回复模式已启动，等待消息中...")
        print("[微信] 按 Ctrl+C 退出")

        while self.running:
            try:
                wechat = uia.WindowControl(ClassName="WeChatMainWndForPC")
                if not wechat.Exists(3, 1):
                    print("[微信] 未检测到微信窗口")
                    time.sleep(10)
                    continue

                wechat.SetTopmost(True)
                time.sleep(0.3)
                wechat.SetTopmost(False)

                list_ctrl = wechat.ListControl(Name="会话")
                if not list_ctrl.Exists(0.5):
                    time.sleep(5)
                    continue

                for item in list_ctrl.GetChildren():
                    try:
                        name = item.Name
                        if not name or name == self.target_chat:
                            continue

                        last_msg = ""
                        msg_item = item.TextControl(foundIndex=2)
                        if msg_item.Exists(0.3):
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

    def _should_reply(self, message: str) -> bool:
        if not config.WECHAT_AUTO_REPLY_ENABLED:
            return False
        for kw in config.WECHAT_REPLY_KEYWORDS:
            if kw in message:
                return True
        return False

    def _reply_to_contact(self, wechat_window, name: str, message: str):
        """回复指定联系人"""
        try:
            wechat_window.SetTopmost(True)
            time.sleep(0.3)

            search_box = wechat_window.EditControl(Name="搜索")
            if search_box.Exists(0.5):
                search_box.Click()
                time.sleep(0.3)
                pyperclip.copy(name)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(1)

            reply = self.assistant.brain.generate_reply(name, message)
            print(f"[回复] -> {name}: {reply}")

            self.assistant.memory.save_contact(name, "wechat", message)
            self.assistant.memory.save_conversation("user", f"[微信-{name}] {message}", source="wechat")
            self.assistant.memory.save_conversation("assistant", reply, source="wechat")

            if self.assistant.subtitle:
                self.assistant.subtitle.push_user(f"[{name}] {message}")
                self.assistant.subtitle.push_assistant(reply)

            edit_box = wechat_window.EditControl(Name="输入信息")
            if edit_box.Exists(0.5):
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
