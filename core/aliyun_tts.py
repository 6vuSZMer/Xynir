import os
import tempfile
import yaml
import pygame
import dashscope
from pathlib import Path
from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat

BASE_DIR = Path(__file__).resolve().parent.parent


class AliyunTTS:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = str(BASE_DIR / "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        tts_cfg = config.get("aliyun_tts", {})
        self.api_key = tts_cfg.get("api_key", "")
        self.model = tts_cfg.get("model", "cosyvoice-v2")
        self.voice = tts_cfg.get("voice", "longfeifei_v2")

        dashscope.api_key = self.api_key

    def speak(self, text):
        """合成语音并播放，播放完成后释放资源"""
        try:
            # 每次调用前重新初始化 SpeechSynthesizer
            synthesizer = SpeechSynthesizer(
                model=self.model,
                voice=self.voice,
                format=AudioFormat.MP3_22050HZ_MONO_256KBPS
            )
            audio_data = synthesizer.call(text)

            if not audio_data:
                print("TTS 返回空音频")
                return

            # 写入临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            # 初始化并播放
            pygame.mixer.init()
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            # 停止播放、卸载音乐、关闭音频设备，确保文件句柄被释放
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            pygame.mixer.quit()

            # 删除临时文件，失败只警告
            try:
                os.unlink(tmp_path)
            except Exception as e:
                print(f"临时文件删除失败（忽略）: {e}")

        except Exception as e:
            print(f"阿里云 TTS 合成失败: {e}")
            raise e