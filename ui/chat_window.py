import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt5.QtCore import Qt, QTimer, pyqtSignal


class ChatWindow(QWidget):
    message_submitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat with Xynir")
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 设置窗口大小和初始位置
        self.resize(300, 150)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - 350, screen.bottom() - 200)

        # 气泡标签
        self.bubble_label = QLabel(self)
        self.bubble_label.setAlignment(Qt.AlignCenter)
        self.bubble_label.setWordWrap(True)
        self.bubble_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.9);
                border-radius: 15px;
                padding: 10px 15px;
                font-family: "Microsoft YaHei", "微软雅黑", sans-serif;
                font-size: 14px;
                color: #333333;
            }
        """)
        self.bubble_label.hide()

        # 输入框
        self.input_box = QLineEdit(self)
        self.input_box.setPlaceholderText("和信儿说点什么...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(120, 120, 120, 0.8);
                border-radius: 15px;
                padding: 8px 12px;
                font-size: 14px;
                font-family: "Microsoft YaHei", "微软雅黑", sans-serif;
                color: #333333;
            }
        """)
        self.input_box.returnPressed.connect(self._on_input_submitted)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(self.bubble_label)
        layout.addWidget(self.input_box)
        self.setLayout(layout)

        # 气泡自动隐藏定时器
        self.bubble_timer = QTimer(self)
        self.bubble_timer.timeout.connect(self.bubble_label.hide)

    def show_bubble(self, text, duration=5000):
        if not text.strip():
            return
        self.bubble_label.setText(text)
        self.bubble_label.adjustSize()
        self.bubble_label.show()
        self.bubble_timer.start(duration)

    def _on_input_submitted(self):
        text = self.input_box.text().strip()
        if text:
            self.message_submitted.emit(text)
            self.input_box.clear()