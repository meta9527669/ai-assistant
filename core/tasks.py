"""
事务处理模块 - 基础任务指令的解析与执行
"""

import os
import re
import subprocess
import webbrowser
from datetime import datetime, timedelta
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None

import config
from core.monitor import SystemMonitor


class TaskHandler:
    """处理用户的基础事务指令"""

    # 指令关键词 -> 处理方法的映射（按优先级排序，越具体越靠前）
    COMMAND_MAP = [
        ("几点", "handle_time"),
        ("时间", "handle_time"),
        ("今天几号", "handle_date"),
        ("今天星期", "handle_date"),
        ("今天日期", "handle_date"),
        ("几号", "handle_date"),
        ("星期几", "handle_date"),
        ("周几", "handle_date"),
        ("日期", "handle_date"),
        ("天气", "handle_weather"),
        ("电脑状态", "handle_system_status"),
        ("系统状态", "handle_system_status"),
        ("电脑怎么样", "handle_system_status"),
        ("cpu", "handle_cpu"),
        ("处理器", "handle_cpu"),
        ("内存", "handle_memory"),
        ("磁盘", "handle_disk"),
        ("硬盘", "handle_disk"),
        ("运行的程序", "handle_processes"),
        ("进程", "handle_processes"),
        ("运行什么", "handle_processes"),
        ("电池", "handle_battery"),
        ("电量", "handle_battery"),
        ("网络", "handle_network"),
        ("截屏", "handle_screenshot"),
        ("关机", "handle_shutdown"),
        ("重启", "handle_restart"),
        ("取消关机", "handle_cancel_shutdown"),
        ("清理内存", "handle_clean_memory"),
        ("结束进程", "handle_kill_process"),
        ("休眠电脑", "handle_pc_sleep"),
        ("睡眠", "handle_sleep_pc"),
        ("打开", "handle_open_app"),
        ("启动", "handle_open_app"),
        ("搜索", "handle_search"),
        ("搜一下", "handle_search"),
        ("提醒", "handle_reminder"),
        ("备忘", "handle_note"),
        ("记一下", "handle_note"),
        ("写日记", "handle_diary"),
        ("日记", "handle_diary"),
        ("音量", "handle_volume"),
        ("静音", "handle_mute"),
        ("截图", "handle_screenshot"),
    ]

    def __init__(self, memory):
        self.memory = memory
        self.reminders: list[dict] = []
        self.monitor = SystemMonitor()

    def try_handle(self, text: str) -> str | None:
        """
        尝试匹配并执行指令
        返回执行结果的文字回复，未匹配返回 None
        """
        for keyword, method_name in self.COMMAND_MAP:
            if keyword in text:
                method = getattr(self, method_name, None)
                if method:
                    return method(text)
        return None

    # ====== 具体任务 ======

    def handle_time(self, text: str) -> str:
        now = datetime.now()
        return f"现在是 {now.strftime('%H点%M分')}。"

    def handle_date(self, text: str) -> str:
        now = datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return f"今天是 {now.strftime('%Y年%m月%d日')} {weekdays[now.weekday()]}。"

    def handle_weather(self, text: str) -> str:
        if not requests or not config.WEATHER_API_KEY:
            city = config.DEFAULT_CITY
            webbrowser.open(f"https://www.baidu.com/s?wd={quote(city + '天气')}")
            return f"已帮你打开{city}天气搜索页面。"

        try:
            city = config.DEFAULT_CITY
            resp = requests.get(
                config.WEATHER_API_URL,
                params={"key": config.WEATHER_API_KEY, "city": city, "extensions": "base"},
                timeout=10,
            )
            data = resp.json()
            if data.get("lives"):
                live = data["lives"][0]
                return (
                    f"{live.get('province', '')}{live.get('city', '')}当前天气："
                    f"{live.get('weather', '未知')}，"
                    f"气温{live.get('temperature', '?')}°C，"
                    f"{live.get('winddirection', '')}风{live.get('windpower', '')}级。"
                )
            return "暂时查不到天气信息呢。"
        except Exception as e:
            return f"天气查询出了点问题: {e}"

    def handle_open_app(self, text: str) -> str:
        app_map = {
            "浏览器": "start chrome",
            "记事本": "notepad",
            "计算器": "calc",
            "资源管理器": "explorer",
            "终端": "start cmd",
            "任务管理器": "taskmgr",
            "设置": "start ms-settings:",
        }
        for app_name, cmd in app_map.items():
            if app_name in text:
                try:
                    subprocess.Popen(cmd, shell=True)
                    return f"已为你打开{app_name}。"
                except Exception:
                    return f"打开{app_name}失败了。"

        match = re.search(r"打开(.+)", text)
        if match:
            app = match.group(1).strip()
            try:
                subprocess.Popen(f"start {app}", shell=True)
                return f"正在尝试打开{app}。"
            except Exception:
                return f"找不到{app}这个应用呢。"
        return "你想打开什么应用？"

    def handle_search(self, text: str) -> str:
        match = re.search(r"搜索(.+)|搜一下(.+)", text)
        query = ""
        if match:
            query = (match.group(1) or match.group(2) or "").strip()
        if not query:
            return "你想搜什么？"
        webbrowser.open(f"https://www.baidu.com/s?wd={quote(query)}")
        return f"已帮你搜索「{query}」。"

    def handle_reminder(self, text: str) -> str:
        time_match = re.search(r"(\d+)分钟", text)
        if time_match:
            minutes = int(time_match.group(1))
            remind_time = datetime.now() + timedelta(minutes=minutes)
        else:
            time_match = re.search(r"(\d+)点(\d+)?", text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                remind_time = datetime.now().replace(hour=hour, minute=minute, second=0)
                if remind_time < datetime.now():
                    remind_time += timedelta(days=1)
            else:
                return "请告诉我提醒时间，比如「10分钟后提醒我开会」或「下午3点提醒我」。"

        content_match = re.search(r"提醒我(.+?)(?:\d|$)", text)
        content = content_match.group(1).strip() if content_match else "待办事项"

        self.reminders.append({"time": remind_time, "content": content})
        self.memory.save_reminder(remind_time, content)
        return f"好的，{remind_time.strftime('%H点%M分')}我会提醒你{content}。"

    def handle_note(self, text: str) -> str:
        match = re.search(r"记一下(.+)|备忘(.+)", text)
        note = match.group(1).strip() if match else text
        self.memory.save_note(note)
        return f"已经记下来了：{note}"

    def handle_diary(self, text: str) -> str:
        return "请告诉我今天想记录什么，我来帮你写日记。"

    def handle_volume(self, text: str) -> str:
        try:
            if "大" in text or "高" in text or "加" in text:
                subprocess.Popen(
                    'powershell -c "Add-Type -TypeDefinition \'using System.Runtime.InteropServices; public class W { [DllImport(\\"user32.dll\")] public static extern int keybd_event(byte b, byte c, uint d, int e); }\' ; [W]::keybd_event(175,0,1,0)"',
                    shell=True,
                )
                return "音量调大了一点。"
            elif "小" in text or "低" in text or "减" in text:
                return "音量调小了一点。"
            return "你想调大还是调小音量？"
        except Exception:
            return "音量调节需要额外权限。"

    def handle_mute(self, text: str) -> str:
        return "已静音。（演示）"

    def handle_screenshot(self, text: str) -> str:
        try:
            import pyautogui

            path = os.path.join(config.DATA_DIR, f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            pyautogui.screenshot(path)
            return f"截图已保存到 {path}。"
        except Exception:
            return "截图功能需要安装 pyautogui。"

    def handle_shutdown(self, text: str) -> str:
        return "确定要关机吗？确认的话请说「确认关机」。（安全确认）"

    def handle_sleep_pc(self, text: str) -> str:
        if "电脑" in text or "pc" in text.lower():
            return "好的，让电脑休息一下。"
        return "你是说让电脑睡眠，还是让自己休息？早点睡哦。"

    # ====== 系统监控 ======

    def handle_system_status(self, text: str) -> str:
        return self.monitor.get_system_status()

    def handle_cpu(self, text: str) -> str:
        return f"CPU使用率: {self.monitor.get_cpu_usage()}"

    def handle_memory(self, text: str) -> str:
        return f"内存: {self.monitor.get_memory_usage()}"

    def handle_disk(self, text: str) -> str:
        return self.monitor.get_disk_usage()

    def handle_processes(self, text: str) -> str:
        return self.monitor.get_running_processes()

    def handle_battery(self, text: str) -> str:
        result = self.monitor.get_battery_status()
        return f"电池: {result}" if result else "没有检测到电池（可能是台式机）。"

    def handle_network(self, text: str) -> str:
        return self.monitor.get_network_status()

    def handle_restart(self, text: str) -> str:
        if "确认" in text:
            return self.monitor.restart()
        return "确定要重启电脑吗？确认的话请说「确认重启」。(1分钟后执行)"

    def handle_cancel_shutdown(self, text: str) -> str:
        return self.monitor.cancel_shutdown()

    def handle_clean_memory(self, text: str) -> str:
        return self.monitor.clean_memory()

    def handle_kill_process(self, text: str) -> str:
        import re
        match = re.search(r"结束(?:进程)?(.+)", text)
        name = match.group(1).strip() if match else ""
        if not name:
            return "要结束哪个进程？比如「结束进程 chrome」"
        return self.monitor.kill_process(name)

    def handle_pc_sleep(self, text: str) -> str:
        return self.monitor.sleep()

    def check_reminders(self) -> str | None:
        """检查是否有到期的提醒"""
        now = datetime.now()
        due = [r for r in self.reminders if r["time"] <= now]
        self.reminders = [r for r in self.reminders if r["time"] > now]
        if due:
            msgs = "；".join(f"该{r['content']}了" for r in due)
            return f"提醒：{msgs}。主人别忘了哦！"
        return None
