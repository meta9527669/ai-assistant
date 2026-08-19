"""
语音模块 - 语音识别（STT）与语音合成（TTS）
"""

import speech_recognition as sr
import pyttsx3
import threading
import queue

import config


class VoiceEngine:
    """语音引擎：负责听（识别）和说（合成）"""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        self.tts = pyttsx3.init()
        voices = self.tts.getProperty("voices")
        zh_voice = None
        for v in voices:
            if "chinese" in v.name.lower() or "zh" in v.id.lower() or "hui" in v.name.lower():
                zh_voice = v
                break
        if zh_voice:
            self.tts.setProperty("voice", zh_voice.id)
        self.tts.setProperty("rate", config.TTS_RATE)
        self.tts.setProperty("volume", config.TTS_VOLUME)

        self._speak_queue: queue.Queue = queue.Queue()
        self._tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self._tts_thread.start()

    def _tts_worker(self):
        while True:
            text = self._speak_queue.get()
            if text is None:
                break
            self.tts.say(text)
            self.tts.runAndWait()
            self._speak_queue.task_done()

    def speak(self, text: str, block: bool = False):
        """语音合成 - 说出一段话"""
        if block:
            self.tts.say(text)
            self.tts.runAndWait()
        else:
            self._speak_queue.put(text)

    def listen(self, timeout: int = 5, phrase_limit: int = 15) -> str | None:
        """
        语音识别 - 听取用户语音并转为文字
        返回识别到的文字，未识别或超时返回 None
        """
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_limit
                )
            except sr.WaitTimeoutError:
                return None

        try:
            text = self.recognizer.recognize_google(audio, language=config.LANGUAGE)
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            try:
                text = self.recognizer.recognize_sphinx(audio, language=config.LANGUAGE)
                return text
            except Exception:
                return None

    def listen_for_wake_word(self) -> bool:
        """持续监听，直到检测到唤醒词"""
        while True:
            text = self.listen(timeout=None, phrase_limit=5)
            if text:
                text_lower = text.lower()
                for wake in config.WAKE_WORDS:
                    if wake.lower() in text_lower:
                        return True
            return False

    def text_input(self) -> str:
        """文本输入模式"""
        return input("你: ").strip()

    def shutdown(self):
        self._speak_queue.put(None)
