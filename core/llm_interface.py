import os
import sys
import time
import json
import re
import base64
import datetime
import threading
import requests
import yaml
from pathlib import Path

from core.memory_manager import MemoryManager

BASE_DIR = Path(__file__).resolve().parent.parent

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


class LLMInterface:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = str(BASE_DIR / "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.api_key = config["llm"]["api_key"]
        self.base_url = config["llm"]["base_url"]
        self.model_name = config["llm"]["model_name"]

        self.memory_manager = MemoryManager()

        self.conversation_history = []
        self.history_max = 12
        self._history_lock = threading.Lock()
        self.load_history()

    def load_history(self):
        history_path = str(BASE_DIR / "data" / "memory" / "conversation_history.json")
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    raw_history = json.load(f)
                self.conversation_history = []
                for msg in raw_history:
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        role = msg["role"]
                        content = msg["content"]
                        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                            if role == "assistant":
                                content = self._extract_natural_reply(content)
                            if content.strip():
                                self.conversation_history.append({"role": role, "content": content.strip()})
                self.conversation_history = self.conversation_history[-self.history_max:]
            except Exception:
                self.conversation_history = []

    def save_history(self):
        history_path = BASE_DIR / "data" / "memory" / "conversation_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = history_path.with_suffix(".json.tmp")
        with self._history_lock:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, history_path)

    def _extract_natural_reply(self, raw_text):
        """尝试从可能包含 JSON 的文本中提取自然语言回复"""
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict) and "reply" in data:
                return data["reply"].strip()
        except Exception:
            pass
        return raw_text.strip()

    def add_to_history(self, user_text, assistant_text):
        user_text = user_text.strip()
        assistant_text = assistant_text.strip()
        if not user_text or not assistant_text:
            return
        assistant_text = self._extract_natural_reply(assistant_text)
        if not assistant_text:
            return
        self.conversation_history.append({"role": "user", "content": user_text})
        self.conversation_history.append({"role": "assistant", "content": assistant_text})
        if len(self.conversation_history) > self.history_max:
            self.conversation_history = self.conversation_history[-self.history_max:]
        self.save_history()

    def chat(self, messages, stream=False):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            # 不再强制 JSON 输出，避免与多轮对话冲突
        }
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
                break
            except Exception as e:
                if attempt == max_attempts:
                    raise Exception(f"API请求失败（重试{max_attempts}次后仍失败）: {e}")
                print(f"请求失败 (第{attempt}次): {e}，正在重试...")
                time.sleep(2)
        if response.status_code != 200:
            raise Exception(f"API请求失败: {response.status_code} {response.text}")
        result = response.json()
        return result["choices"][0]["message"]["content"]

    def chat_with_emotion_stream(self, user_input):
        with open(BASE_DIR / "prompts" / "chat_emotion.txt", "r", encoding="utf-8") as f:
            system_prompt = f.read()

        # 注入时间观念
        now = datetime.datetime.now()
        weekday = ['一', '二', '三', '四', '五', '六', '日'][now.weekday()]
        time_context = f"现在是{now.month}月{now.day}日，星期{weekday}，{now.hour}点{now.minute}分。"
        system_prompt += "\n\n" + time_context

        # 注入上次互动间隔
        last = self.memory_manager.relationship.get("last_interaction")
        if last:
            hours_since = (time.time() - last) / 3600
            if hours_since > 24:
                system_prompt += f"你们已经有 {int(hours_since/24)} 天没聊天了。"
            elif hours_since > 1:
                system_prompt += f"你们已经 {int(hours_since)} 小时没聊天了。"

        # 注入关系背景
        relationship_context = self.memory_manager.get_relationship_context()
        system_prompt += "\n\n" + relationship_context

        # 注入长期记忆
        clear_memories, vague_memories, flashback = self.memory_manager.get_memory_injection()
        memory_text = ""
        if clear_memories:
            memory_text += "你清晰记得关于主人的事情：\n"
            for mem in clear_memories:
                memory_text += f"- {mem}\n"
        if vague_memories:
            memory_text += "\n你隐约记得一些事情：\n"
            for mem in vague_memories:
                memory_text += f"- {mem}\n"
        if flashback:
            memory_text += f"\n你突然想起：{flashback}\n"
        if memory_text:
            system_prompt += "\n\n" + memory_text

        # 构建消息：system + 清洗后的历史 + 当前用户
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})

        raw_response = self.chat(messages)

        # 如果回复为空，打印警告并用默认回复
        if not raw_response or not raw_response.strip():
            print("⚠️ LLM 返回空回复，使用默认回复")
            raw_response = "（沉默了一会儿）"

        result = self._parse_emotion_json(raw_response)
        reply_text = result.get("reply", "")
        if not reply_text.strip():
            reply_text = raw_response.strip()
            result["reply"] = reply_text

        # 模拟流式打印
        print("信儿：", end="", flush=True)
        for char in reply_text:
            print(char, end="", flush=True)
        print()

        if reply_text.strip():
            self.add_to_history(user_input, reply_text)
            self.memory_manager.update_relationship(closeness_delta=1, mood=result.get("emotion") or "neutral")

        return result

    def _parse_emotion_json(self, raw):
        result = {"reply": "", "action": "", "emotion": "neutral", "motion": "", "params": []}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                result.update(data)
        except Exception:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                    if isinstance(data, dict):
                        result.update(data)
                except Exception:
                    pass

        reply = result.get("reply", "").strip()

        # 清理方括号和圆括号动作描述
        bracket_match = re.search(r'\[(.*?)\]', reply)
        if bracket_match:
            if not result.get("action"):
                result["action"] = bracket_match.group(1).strip()
            reply = re.sub(r'\[.*?\]', '', reply).strip()

        paren_match = re.search(r'[（(](.*?)[)）]', reply)
        if paren_match:
            if not result.get("action"):
                result["action"] = paren_match.group(1).strip()
            reply = re.sub(r'[（(].*?[)）]', '', reply).strip()

        result["reply"] = re.sub(r'\n\s*\n', '\n', reply).strip()
        if not result["reply"]:
            result["reply"] = raw.strip()
        return result

    def extract_and_store_memories(self, user_input, assistant_reply):
        prompt = (
            "你是一个严格的记忆提取助手。只提取用户（主人）明确表达的持久性事实或偏好。"
            "不要提取寒暄、提问、情绪表达或一次性的对话内容。"
            "每条事实必须以主语开头，明确是'用户'或'主人'，例如'用户喜欢吃草莓'。"
            "如果事实重要度低于4，不要提取。"
            f"\n对话内容：\n用户：{user_input}\n信儿：{assistant_reply}\n"
            "请返回JSON数组，每个元素包含 'text' 和 'importance'（4或5）。"
        )
        messages = [
            {"role": "system", "content": "你是一个严格的记忆提取助手。"},
            {"role": "user", "content": prompt}
        ]
        raw = self.chat(messages)
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                facts = json.loads(match.group())
                for fact in facts:
                    text = fact.get("text", "").strip()
                    importance = fact.get("importance", 3)
                    if not text or importance < 4:
                        continue
                    if any(q in text for q in ['?', '？', '什么', '怎么', '为什么', '吗', '呢', '吧']):
                        continue
                    self.memory_manager.add_or_update_fact(text, importance, "neutral", subject="user")
        except Exception as e:
            print(f"记忆提取失败: {e}")

    def get_action(self, screenshot_bytes, task_context):
        # 保留原有实现，此处省略
        pass

    def get_plan(self, screenshot_bytes, task_context):
        # 保留原有实现，此处省略
        pass

    def parse_action(self, raw):
        try:
            return json.loads(raw)
        except Exception:
            pass
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return {"action": "unknown"}