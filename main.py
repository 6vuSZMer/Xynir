import os
import sys
import time
import base64
import threading

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--ignore-gpu-blocklist "
    "--enable-gpu-rasterization "
    "--enable-accelerated-2d-canvas "
    "--disable-software-rasterizer "
    "--use-gl=desktop"
)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QSurfaceFormat
from PyQt5.QtCore import QTimer, QObject, pyqtSignal

from core.action import execute_action, find_element_by_description
from core.llm_interface import LLMInterface
from core.screen_parser import ScreenParser
from core.speech import SpeechManager
from utils.screen import grab_screen
from ui.live2d_window import Live2DWindow
from ui.chat_window import ChatWindow


def setup_opengl_format():
    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)


# 全局信号
class WorkerSignals(QObject):
    result_ready = pyqtSignal(str, str, str, str, list)  # reply, action, emotion, motion, params
    error_occurred = pyqtSignal(str)

worker_signals = WorkerSignals()


def update_live2d_ui(window, chat_window, reply, action, emotion, motion, params):
    print(f"🎨 更新 UI：reply={reply}, action={action}, emotion={emotion}, motion={motion}, params={params}", flush=True)
    if hasattr(window, 'live2d_widget'):
        widget = window.live2d_widget
        try:
            widget.set_mood(emotion)
        except Exception as e:
            print(f"❌ 设置情绪失败: {e}", flush=True)
        if motion:
            try:
                widget.play_motion(motion, 0, 10)
            except Exception as e:
                print(f"❌ 播放动作失败: {e}", flush=True)
        if params:
            try:
                widget.apply_params(params)
            except Exception as e:
                print(f"❌ 应用 Live2D 参数失败: {e}", flush=True)
    # 显示气泡的
    try:
        chat_window.show_bubble(reply)
    except Exception as e:
        print(f"❌ 显示气泡失败: {e}", flush=True)
    # 播放语音的
    if reply.strip():
        try:
            speech_manager.speak(reply)
        except Exception as e:
            print(f"❌ 播放语音失败: {e}", flush=True)
    print("✅ Live2D 状态更新成功", flush=True)


def handle_user_message(window, chat_window, llm, text):
    def worker():
        print("🚀 后台线程开始调用 LLM...", flush=True)
        try:
            result = llm.chat_with_emotion_stream(text)
            reply = result.get("reply", "")
            action = result.get("action", "")
            emotion = result.get("emotion", "neutral")
            motion = result.get("motion", "")
            params = result.get("params", [])
            worker_signals.result_ready.emit(reply, action, emotion, motion, params)

            threading.Thread(target=llm.extract_and_store_memories, args=(text, reply), daemon=True).start()
        except Exception as e:
            worker_signals.error_occurred.emit(str(e))

    threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    setup_opengl_format()
    app = QApplication(sys.argv)

    llm = LLMInterface()
    speech_manager = SpeechManager()

    live2d_window = Live2DWindow()
    chat_window = ChatWindow()

    live2d_window.show()
    chat_window.show()

    worker_signals.result_ready.connect(
        lambda r, a, e, m, p: update_live2d_ui(live2d_window, chat_window, r, a, e, m, p)
    )
    def _show_error(err):
        print(f"❌ 后台线程出wrong: {err}", flush=True)
        try:
            chat_window.show_bubble(f"⚠️ {err}")
        except Exception:
            pass

    worker_signals.error_occurred.connect(_show_error)
    chat_window.message_submitted.connect(
        lambda text: handle_user_message(live2d_window, chat_window, llm, text)
    )

    sys.exit(app.exec_())