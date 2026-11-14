import pyautogui
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController
import time
import random
import difflib
import re

mouse = MouseController()
keyboard = KeyboardController()


def execute_action(action_dict):
    action = action_dict.get("action", "unknown")

    # ---------- 点击 ----------
    if action == "click":
        x = int(action_dict.get("x", 0))
        y = int(action_dict.get("y", 0))

        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(random.uniform(0.1, 0.3))
        mouse.click(Button.left, 1)
        print(f"点击了坐标 ({x}, {y})")
        return True

    # ---------- 输入文字 ----------
    if action == "type":
        text = action_dict.get("input_text", "")
        if not text:
            print("❌ 缺少 input_text，无法输入")
            return False

        # 如果给了坐标，先点击确保焦点正确
        x = action_dict.get("x", None)
        y = action_dict.get("y", None)
        if x is not None and y is not None:
            pyautogui.moveTo(int(x), int(y), duration=0.3)
            time.sleep(random.uniform(0.1, 0.2))
            mouse.click(Button.left, 1)
            time.sleep(0.15)

        pyautogui.typewrite(text, interval=random.uniform(0.05, 0.1))
        print(f"输入了文字: {text}")
        return True

    # ---------- 按键 ----------
    if action == "key":
        key_name = action_dict.get("key", "")
        if not key_name:
            print("❌ 缺少 key，无法按键")
            return False

        special_keys = {
            "enter": Key.enter,
            "esc": Key.esc,
            "tab": Key.tab,
            "space": Key.space,
            "backspace": Key.backspace,
            "delete": Key.delete,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
            "win": Key.cmd,
            "shift": Key.shift,
            "ctrl": Key.ctrl,
            "alt": Key.alt,
        }

        if key_name.lower() in special_keys:
            keyboard.press(special_keys[key_name.lower()])
            keyboard.release(special_keys[key_name.lower()])
        else:
            keyboard.press(key_name)
            keyboard.release(key_name)

        print(f"按下了按键: {key_name}")
        return True

    # ---------- 等待 ----------
    if action == "wait":
        seconds = action_dict.get("seconds", 1)
        if isinstance(seconds, (int, float)) and seconds > 0:
            print(f"等待 {seconds} 秒...")
            time.sleep(seconds)
            return True
        else:
            print("❌ seconds 参数无效")
            return False

    # ---------- 完成或未知 ----------
    if action == "done":
        print("✅ 任务标记完成")
        return True

    if action == "unknown":
        print("❓ LLM 不知道该怎么办")
        return False

    print(f"❌ 未知的动作类型: {action}")
    return False


def normalize_text(s):
    """统一小写，去掉空格和特殊符号，只保留中英文和数字"""
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', s)
    return s


def find_element_by_description(elements, step):
    target_desc = normalize_text(step.get("target_description", ""))
    hints = [normalize_text(h) for h in step.get("hint_keywords", [])]

    # 优先考虑可交互元素
    interactive_elements = [el for el in elements if el.get("interactivity", False)]
    if not interactive_elements:
        interactive_elements = elements

    # 1. 精确/包含匹配
    for el in interactive_elements:
        content = normalize_text(el.get("content", ""))
        if not content:
            continue
        if target_desc and (target_desc in content or content in target_desc):
            return el
        for hint in hints:
            if hint and (hint in content or content in hint):
                return el

    # 2. 关键词分词匹配
    keywords = set()
    if target_desc:
        keywords.update(target_desc.split())
    for hint in hints:
        keywords.update(hint.split())
    keywords = {k for k in keywords if len(k) >= 2}

    for el in interactive_elements:
        content = normalize_text(el.get("content", ""))
        if not content:
            continue
        if any(k in content for k in keywords):
            return el

    # 3. 模糊相似度匹配
    best_el = None
    best_ratio = 0.0
    for el in interactive_elements:
        content = normalize_text(el.get("content", ""))
        if not content:
            continue
        for text in [target_desc] + hints:
            if text and content:
                ratio = difflib.SequenceMatcher(None, text, content).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_el = el

    if best_ratio >= 0.4:
        return best_el

    return None