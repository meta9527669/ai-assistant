"""
大脑模块 - 基于 LLM 的对话与情感陪伴
"""

import json

try:
    import requests
except ImportError:
    requests = None

import config


class Brain:
    """李亦禾的「大脑」：处理自然语言对话和情感交互"""

    def __init__(self):
        self.history: list[dict] = []
        self.max_history = 20  # 保留最近 20 轮对话

    def chat(self, user_message: str, context: str = "") -> str:
        """
        与用户对话，返回李亦禾的回复
        context: 可选的额外上下文（如当前情绪、场景信息）
        """
        messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]

        if context:
            messages.append({"role": "system", "content": f"当前场景信息: {context}"})

        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})

        reply = self._call_llm(messages)

        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": reply})

        if len(self.history) > self.max_history * 2:
            self.history = self.history[-(self.max_history * 2):]

        return reply

    def generate_reply(self, sender: str, message: str) -> str:
        """
        为微信/QQ消息生成自动回复
        """
        prompt = (
            f"你的主人收到了一条来自「{sender}」的消息：「{message}」\n"
            "请以主人的口吻生成一条简洁、得体的回复（30字以内），"
            "帮主人得体地回复对方。只输出回复内容，不要加引号或说明。"
        )
        messages = [
            {"role": "system", "content": "你是李亦禾，帮主人回复消息的助手。回复简洁得体。"},
            {"role": "user", "content": prompt},
        ]
        return self._call_llm(messages).strip().strip('"').strip("'")

    def _call_llm(self, messages: list[dict]) -> str:
        """调用 OpenAI 兼容 API"""
        if requests is None:
            return "抱歉，大模型依赖未安装，请运行 pip install requests。"

        try:
            resp = requests.post(
                f"{config.LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.LLM_MODEL,
                    "messages": messages,
                    "max_tokens": config.LLM_MAX_TOKENS,
                    "temperature": config.LLM_TEMPERATURE,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"（思考中出了一点小状况: {e}）"

    def clear_history(self):
        self.history.clear()

    def get_history(self) -> list[dict]:
        return self.history.copy()
