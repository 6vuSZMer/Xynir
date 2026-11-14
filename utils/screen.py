import mss
import mss.tools
# mss 系统工具

# 抓取屏幕
def grab_screen(monitor_index=1):
    # monitor_index 截取屏幕
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        screenshot = sct.grab(monitor)
        return mss.tools.to_png(screenshot.rgb, screenshot.size)