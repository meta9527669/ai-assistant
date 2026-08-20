# 云端迷你李亦禾 - 部署指南

## 功能
- 手机微信直接对话（电脑关机也能用）
- 情感对话 (DeepSeek API)
- 远程开机 (Wake-on-LAN)
- 备忘/提醒
- 网页版（浏览器也能用）

## 部署到 PythonAnywhere (免费)

### 1. 注册 PythonAnywhere
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
- 编辑 `app.py`，确认:
  - `API_KEY` (DeepSeek API Key)
  - `PC_MAC` (电脑MAC地址)
  - `WECHAT_TOKEN` (与公众号后台一致)

### 7. 重新加载
- Web 标签 → 点击 Reload

## 微信公众号配置

### 注册公众号
1. 访问 https://mp.weixin.qq.com
2. 注册「订阅号」(个人免费, 需要身份证)
3. 注册成功后，进入公众号后台

### 配置服务器
1. 公众号后台 → 设置与开发 → 基本配置
2. 找到「服务器配置」→ 点击「修改配置」
3. 填写:
   - URL: `https://你的用户名.pythonanywhere.com/wechat`
   - Token: `liyihe2026` (与 app.py 中 WECHAT_TOKEN 一致)
   - EncodingAESKey: 随机生成
   - 消息加解密方式: 明文模式
4. 点击「提交」(PythonAnywhere 需已部署)
5. 显示「提交成功」即配置完成

### 使用
1. 手机微信搜索你的公众号名称并关注
2. 直接在公众号里发消息
3. 李亦禾会自动回复
4. 电脑关机也能用！

## 远程开机配置

### 电脑端 WoL 设置
1. 重启电脑，进入 BIOS/UEFI
2. Power Management → Wake-on-LAN → Enable
3. 设备管理器 → 网络适配器 → 属性
4. 电源管理 → 勾选「允许此设备唤醒计算机」
5. 高级 → 唤醒魔包 → Enable

### 路由器端口转发 (外网开机)
- PythonAnywhere 的 WoL 可能被防火墙拦截
- 建议在路由器上转发 UDP 端口 9 到电脑 IP
- 或用 ngrok 在电脑开机时暴露本地服务

## 网页版访问
- 部署完成后，浏览器打开 `https://你的用户名.pythonanywhere.com`
- 手机也能访问，可添加到桌面作为 PWA
