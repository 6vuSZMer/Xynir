import os
import sys
import live2d.v3 as live2d
from PyQt5.QtWidgets import QApplication, QMainWindow, QOpenGLWidget
from PyQt5.QtCore import Qt, QTimer

class Live2DWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self._loaded = False
        self.mood = "neutral"

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)

    def initializeGL(self):
        live2d.init()
        self.model = live2d.LAppModel()
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'assets', 'live2d', 'model', 'hiyori_free_t08.model3.json'
        )
        if self.model.LoadModelJson(model_path):
            self.model.Resize(400, 600)
            self._loaded = True
            print("✅ Live2D 模型初始化成功")
        else:
            print("❌ 模型加载失败")

    def resizeGL(self, w, h):
        if self._loaded and self.model:
            self.model.Resize(w, h)

    def paintGL(self):
        if self._loaded and self.model:
            self.model.Update()
            self.model.Draw()

    def set_mood(self, emotion):
        self.mood = emotion or "neutral"

    def play_motion(self, motion, group=0, priority=10):
        if not motion or not self._loaded or not self.model:
            return
        try:
            self.model.StartMotion(motion, int(group), int(priority))
        except Exception as e:
            print(f"播放动作失败（忽略）: {e}")

    def apply_params(self, params):
        if not params or not self._loaded or not self.model:
            return
        for p in params:
            if not isinstance(p, dict):
                continue
            name = p.get("name")
            value = p.get("value")
            if name is None or value is None:
                continue
            try:
                self.model.SetParameterValue(str(name), float(value))
            except Exception as e:
                print(f"设置 Live2D 参数失败（忽略）: {e}")

    def dispose(self):
        self._timer.stop()
        try:
            if hasattr(live2d, "dispose"):
                live2d.dispose()
        except Exception:
            pass
        self.model = None
        self._loaded = False


class Live2DWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xynir")
        self.setGeometry(500, 200, 400, 600)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.live2d_widget = Live2DWidget(self)
        self.setCentralWidget(self.live2d_widget)

    def closeEvent(self, event):
        if hasattr(self.live2d_widget, "dispose"):
            self.live2d_widget.dispose()
        super().closeEvent(event)
