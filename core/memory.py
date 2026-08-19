"""
记忆模块 - 对话记录、备忘、日记、提醒存储
"""

import os
import sqlite3
import json
from datetime import datetime

import config


class Memory:
    """李亦禾的记忆系统：基于 SQLite 的持久化存储"""

    def __init__(self):
        for d in [config.DATA_DIR, config.CHAT_LOG_DIR, config.DIARY_DIR]:
            os.makedirs(d, exist_ok=True)

        self.conn = sqlite3.connect(config.MEMORY_DB_PATH, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT DEFAULT 'voice'
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                remind_time TEXT NOT NULL,
                content TEXT NOT NULL,
                done INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                content TEXT NOT NULL,
                mood TEXT
            );
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                platform TEXT NOT NULL,
                last_message TEXT,
                last_time TEXT
            );
        """)
        self.conn.commit()

    def save_conversation(self, role: str, content: str, source: str = "voice"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO conversations (role, content, timestamp, source) VALUES (?, ?, ?, ?)",
            (role, content, ts, source),
        )
        self.conn.commit()

        log_file = os.path.join(config.CHAT_LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.jsonl")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"role": role, "content": content, "ts": ts, "source": source}) + "\n")

    def save_note(self, content: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO notes (content, created_at) VALUES (?, ?)",
            (content, ts),
        )
        self.conn.commit()

    def save_reminder(self, remind_time: datetime, content: str):
        self.conn.execute(
            "INSERT INTO reminders (remind_time, content) VALUES (?, ?)",
            (remind_time.strftime("%Y-%m-%d %H:%M:%S"), content),
        )
        self.conn.commit()

    def save_diary(self, content: str, mood: str = ""):
        date = datetime.now().strftime("%Y-%m-%d")
        self.conn.execute(
            "INSERT INTO diary (date, content, mood) VALUES (?, ?, ?)",
            (date, content, mood),
        )
        self.conn.commit()
        diary_file = os.path.join(config.DIARY_DIR, f"{date}.md")
        with open(diary_file, "a", encoding="utf-8") as f:
            f.write(f"\n## {datetime.now().strftime('%H:%M')}\n\n{content}\n")
            if mood:
                f.write(f"\n*心情: {mood}*\n")

    def save_contact(self, name: str, platform: str, last_message: str = ""):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute("""
            INSERT INTO contacts (name, platform, last_message, last_time)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                last_message = excluded.last_message,
                last_time = excluded.last_time
        """, (name, platform, last_message, ts))
        self.conn.commit()

    def get_recent_conversations(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content, timestamp FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in reversed(rows)]

    def get_notes(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT content, created_at FROM notes ORDER BY id DESC"
        ).fetchall()
        return [{"content": r[0], "created_at": r[1]} for r in rows]

    def get_pending_reminders(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT remind_time, content FROM reminders WHERE done = 0 ORDER BY remind_time"
        ).fetchall()
        return [{"remind_time": r[0], "content": r[1]} for r in rows]

    def get_diary(self, date: str = "") -> list[dict]:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT date, content, mood FROM diary WHERE date = ? ORDER BY id",
            (date,),
        ).fetchall()
        return [{"date": r[0], "content": r[1], "mood": r[2]} for r in rows]

    def close(self):
        self.conn.close()
