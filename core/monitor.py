"""
系统监控模块 - 检测电脑状态，提供系统信息和告警

功能：
  - CPU/内存/磁盘/网络/电池 实时状态
  - 高占用进程检测
  - 自动告警（CPU>80%, 内存>85%, 磁盘<10%, 电池<20%）
  - 系统控制（关机/重启/休眠/清理）
"""

import os
import time
import subprocess
import socket
from datetime import datetime, timedelta
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

import config


class SystemMonitor:
    """电脑系统状态监控"""

    def __init__(self):
        self._boot_time = psutil.boot_time() if psutil else time.time()
        self._last_alerts: set = set()
        self._alert_cooldown = 300  # 5分钟内不重复告警

    # ==================== 状态查询 ====================

    def get_system_status(self) -> str:
        """获取完整系统状态报告"""
        parts = []

        cpu = self.get_cpu_usage()
        parts.append(f"CPU: {cpu}")

        mem = self.get_memory_usage()
        parts.append(f"内存: {mem}")

        disk = self.get_disk_usage()
        parts.append(f"磁盘: {disk}")

        battery = self.get_battery_status()
        if battery:
            parts.append(f"电池: {battery}")

        uptime = self.get_uptime()
        parts.append(f"运行: {uptime}")

        return "\n".join(parts)

    def get_cpu_usage(self) -> str:
        """CPU 使用率"""
        if not psutil:
            return "需要安装 psutil"
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cores = psutil.cpu_count()
            freq = psutil.cpu_freq()
            freq_str = f", {freq.current:.0f}MHz" if freq else ""
            return f"{cpu_percent}% ({cores}核{freq_str})"
        except Exception:
            return "无法读取CPU"

    def get_memory_usage(self) -> str:
        """内存使用情况"""
        if not psutil:
            return "需要安装 psutil"
        try:
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024**3)
            used_gb = mem.used / (1024**3)
            return f"{used_gb:.1f}/{total_gb:.1f}GB ({mem.percent}%)"
        except Exception:
            return "无法读取内存"

    def get_disk_usage(self) -> str:
        """磁盘使用情况"""
        if not psutil:
            return "需要安装 psutil"
        try:
            disk = psutil.disk_usage("/")
            total_gb = disk.total / (1024**3)
            used_gb = disk.used / (1024**3)
            free_gb = disk.free / (1024**3)
            return f"已用{used_gb:.0f}/{total_gb:.0f}GB, 剩余{free_gb:.0f}GB ({disk.percent}%)"
        except Exception:
            # Windows 可能用 C:
            try:
                disk = psutil.disk_usage("C:\\")
                total_gb = disk.total / (1024**3)
                used_gb = disk.used / (1024**3)
                free_gb = disk.free / (1024**3)
                return f"C盘: 已用{used_gb:.0f}/{total_gb:.0f}GB, 剩余{free_gb:.0f}GB ({disk.percent}%)"
            except Exception:
                return "无法读取磁盘"

    def get_battery_status(self) -> Optional[str]:
        """电池状态"""
        if not psutil:
            return None
        try:
            battery = psutil.sensors_battery()
            if not battery:
                return None
            charging = "充电中" if battery.power_plugged else "未充电"
            return f"{battery.percent}% ({charging})"
        except Exception:
            return None

    def get_running_processes(self) -> str:
        """获取高占用进程"""
        if not psutil:
            return "需要安装 psutil"
        try:
            procs = []
            for p in psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_percent"]
            ):
                try:
                    info = p.info
                    procs.append(info)
                except Exception:
                    continue

            procs.sort(key=lambda x: x.get("memory_percent", 0) or 0, reverse=True)
            top = procs[:8]

            lines = ["占用最高的进程:"]
            for p in top:
                name = p.get("name", "?")
                mem = p.get("memory_percent", 0) or 0
                cpu = p.get("cpu_percent", 0) or 0
                lines.append(f"  {name}: 内存{mem:.1f}%, CPU {cpu:.1f}%")

            return "\n".join(lines)
        except Exception as e:
            return f"进程查询失败: {e}"

    def get_network_status(self) -> str:
        """网络状态"""
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)

            # 测试外网连通性
            try:
                s = socket.create_connection(("8.8.8.8", 53), timeout=3)
                s.close()
                internet = "正常"
            except Exception:
                internet = "断开"

            return f"主机: {hostname}, IP: {local_ip}, 网络: {internet}"
        except Exception:
            return "无法获取网络信息"

    def get_uptime(self) -> str:
        """系统运行时间"""
        if not psutil:
            return "未知"
        try:
            uptime_sec = time.time() - self._boot_time
            days = int(uptime_sec // 86400)
            hours = int((uptime_sec % 86400) // 3600)
            mins = int((uptime_sec % 3600) // 60)
            if days > 0:
                return f"{days}天{hours}小时"
            return f"{hours}小时{mins}分钟"
        except Exception:
            return "未知"

    def get_screenshot(self) -> str:
        """截屏并保存"""
        try:
            import pyautogui

            path = os.path.join(
                config.DATA_DIR,
                f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            )
            pyautogui.screenshot(path)
            return path
        except Exception as e:
            return f"截屏失败: {e}"

    # ==================== 自动告警 ====================

    def check_alerts(self) -> Optional[str]:
        """检查系统告警，返回告警消息"""
        if not psutil:
            return None

        alerts = []

        # CPU 过高
        try:
            cpu = psutil.cpu_percent(interval=2)
            if cpu > 80:
                key = "cpu_high"
                if key not in self._last_alerts:
                    alerts.append(f"CPU使用率{cpu:.0f}%，偏高")
                    self._last_alerts.add(key)
            else:
                self._last_alerts.discard("cpu_high")
        except Exception:
            pass

        # 内存过高
        try:
            mem = psutil.virtual_memory()
            if mem.percent > 85:
                key = "mem_high"
                if key not in self._last_alerts:
                    alerts.append(f"内存使用率{mem.percent}%，偏高")
                    self._last_alerts.add(key)
            else:
                self._last_alerts.discard("mem_high")
        except Exception:
            pass

        # 磁盘空间不足
        try:
            disk = psutil.disk_usage("C:\\")
            if disk.percent > 90:
                key = "disk_low"
                if key not in self._last_alerts:
                    free_gb = disk.free / (1024**3)
                    alerts.append(f"C盘剩余{free_gb:.0f}GB，空间不足")
                    self._last_alerts.add(key)
            else:
                self._last_alerts.discard("disk_low")
        except Exception:
            pass

        # 电池低
        try:
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged and battery.percent < 20:
                key = "battery_low"
                if key not in self._last_alerts:
                    alerts.append(f"电池{battery.percent}%，需要充电")
                    self._last_alerts.add(key)
            else:
                self._last_alerts.discard("battery_low")
        except Exception:
            pass

        if alerts:
            return "系统告警: " + "；".join(alerts)
        return None

    # ==================== 系统控制 ====================

    def shutdown(self) -> str:
        """关机"""
        try:
            subprocess.Popen("shutdown /s /t 60", shell=True)
            return "电脑将在1分钟后关机。说「取消关机」可以撤销。"
        except Exception as e:
            return f"关机失败: {e}"

    def restart(self) -> str:
        """重启"""
        try:
            subprocess.Popen("shutdown /r /t 60", shell=True)
            return "电脑将在1分钟后重启。说「取消关机」可以撤销。"
        except Exception as e:
            return f"重启失败: {e}"

    def cancel_shutdown(self) -> str:
        """取消关机"""
        try:
            subprocess.Popen("shutdown /a", shell=True)
            return "已取消关机/重启。"
        except Exception:
            return "取消失败"

    def sleep(self) -> str:
        """休眠"""
        try:
            subprocess.Popen(
                'powershell -c "Add-Type -Assembly System.Windows.Forms; '
                '[System.Windows.Forms.Application]::SetSuspendState('
                "[System.Windows.Forms.PowerState]::Suspend, $false, $false)\"",
                shell=True,
            )
            return "电脑已休眠。"
        except Exception:
            return "休眠失败"

    def kill_process(self, name: str) -> str:
        """结束进程"""
        try:
            killed = 0
            for p in psutil.process_iter(["name"]):
                if name.lower() in (p.info.get("name", "") or "").lower():
                    try:
                        p.terminate()
                        killed += 1
                    except Exception:
                        pass
            if killed:
                return f"已结束 {killed} 个 {name} 进程。"
            return f"没有找到 {name} 进程。"
        except Exception as e:
            return f"结束进程失败: {e}"

    def clean_memory(self) -> str:
        """清理内存（结束高占用非系统进程）"""
        if not psutil:
            return "需要安装 psutil"
        try:
            # 找内存占用最高的非系统进程
            system_pids = {0, 4}  # System, System
            cleaned = []
            for p in psutil.process_iter(["pid", "name", "memory_percent"]):
                try:
                    if p.info["pid"] in system_pids:
                        continue
                    name = p.info.get("name", "")
                    # 不结束关键进程
                    if name.lower() in (
                        "explorer.exe", "wechat.exe", "svchost.exe",
                        "csrss.exe", "wininit.exe", "services.exe",
                        "lsass.exe", "winlogon.exe",
                    ):
                        continue
                    if (p.info.get("memory_percent") or 0) > 5:
                        p.terminate()
                        cleaned.append(name)
                except Exception:
                    continue

            if cleaned:
                return f"已清理: {', '.join(cleaned[:5])}，释放了一些内存。"
            return "当前没有需要清理的高占用进程。"
        except Exception as e:
            return f"清理失败: {e}"
