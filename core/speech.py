import threading
import pyttsx3
from core.aliyun_tts import AliyunTTS


class SpeechManager:
    def __init__(self):
        # 离线 TTS 备用
        self.tts_engine = None
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 180)
            self.tts_engine.setProperty('volume', 0.9)
        except Exception as e:
            print(f"离线 TTS 初始化失败: {e}")

        # 阿里云 TTS
        self.aliyun_tts = AliyunTTS()

    def speak(self, text):
        if not text or not text.strip():
            return

        def _speak():
            try:
                self.aliyun_tts.speak(text)
            except Exception as e:
                print(f"阿里云 TTS 失败，回退离线语音: {e}")
                if self.tts_engine:
                    try:
                        self.tts_engine.say(text)
                        self.tts_engine.runAndWait()
                    except Exception as e2:
                        print(f"离线 TTS 也失败: {e2}")

        threading.Thread(target=_speak, daemon=True).start()