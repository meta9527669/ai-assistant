"""
Wake-on-LAN 模块 - 远程开机

原理: 发送魔术包 (6字节0xFF + 16次MAC地址) 到目标MAC地址
要求: 目标主板的 BIOS/UEFI 已开启 Wake-on-LAN
"""

import socket
import struct


def wake_on_lan(mac_address: str, broadcast: str = "255.255.255.255", port: int = 9) -> bool:
    """发送 WoL 魔术包唤醒目标主机"""
    mac = mac_address.replace("-", "").replace(":", "").replace(" ", "").replace(".", "")
    if len(mac) != 12:
        return False

    try:
        mac_bytes = bytes.fromhex(mac)
    except ValueError:
        return False

    magic_packet = b'\xff' * 6 + mac_bytes * 16

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, (broadcast, port))
        sock.close()
        return True
    except Exception as e:
        print(f"[WoL] 发送失败: {e}")
        return False


def wake_pc(mac_address: str = None, broadcast: str = None) -> str:
    """唤醒电脑"""
    if not mac_address:
        try:
            import config
            mac_address = config.PC_MAC_ADDRESS
            if not broadcast:
                broadcast = config.WOL_BROADCAST
        except ImportError:
            pass

    if not mac_address or mac_address == "YOUR_PC_MAC":
        return ("未配置电脑MAC地址。请在 config.py 中设置 PC_MAC_ADDRESS。\n"
                "查看方法: 打开cmd输入 ipconfig /all，找物理地址。")

    if not broadcast:
        broadcast = "255.255.255.255"

    success = wake_on_lan(mac_address, broadcast)
    if success:
        return f"开机信号已发送！电脑 ({mac_address}) 正在启动，请等1-2分钟。"
    else:
        return "开机信号发送失败。请确认电脑主板已开启 WoL (BIOS设置)。"
