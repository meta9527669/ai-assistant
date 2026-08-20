# 云端迷你李亦禾 - 部署指南

## 功能
- 手机浏览器访问，电脑关机也能用
- 情感对话 (DeepSeek API)
- 远程开机 (Wake-on-LAN)
- 备忘/提醒
- 不需要电脑开机

## 部署到 PythonAnywhere (免费)

### 1. 注册
访问 https://www.pythonanywhere.com 注册免费账号

### 2. 创建 Web App
- Dashboard → Web → Add a new web app
- 选择 Manual configuration → Python 3.10

### 3. 上传文件
- 打开 Files 标签
- 进入 `/home/你的用户名/mysite/`
- 上传 `app.py` 和 `requirements.txt`

### 4. 安装依赖
- 打开 Consoles → Bash
- 运行: `pip install flask requests`

### 5. 配置 WSGI
- Web 标签 → WSGI configuration file
- 编辑为:
```python
import sys
sys.path.append('/home/你的用户名/mysite')
from app import app as application
```

### 6. 修改配置
- 编辑 `app.py`，确认 API_KEY 和 PC_MAC 正确

### 7. 访问
- 浏览器打开 `https://你的用户名.pythonanywhere.com`
- 手机也可以访问

## 远程开机配置

### 电脑端 WoL 设置
1. 重启电脑，进入 BIOS/UEFI
2. 找到 Power Management → Wake-on-LAN → Enable
3. 找到 Network Boot / PXE → Enable
4. 保存退出

### Windows 网卡设置
1. 设备管理器 → 网络适配器 → 属性
2. 电源管理 → 勾选"允许此设备唤醒计算机"
3. 高级 → 唤醒功能 → Magic Packet → Enable

### 路由器端口转发 (外网开机)
1. 請求转发 UDP 端口 7 和 9 到电脑 IP
2. 或者: 在路由器上设置静态 ARP 绑定电脑 IP

### 注意
- 云端 WoL: 需要路由器端口转发，云端发广播包到你的公网IP
- 同一WiFi WoL: 手机和电脑在同一网络时直接可用
- 如果免费 PythonAnywhere 不支持 UDP socket，可用 ngrok 在电脑开机时暴露本地服务作为中继
