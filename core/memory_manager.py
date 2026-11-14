import json
import os
import time
import random
import math
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class MemoryManager:
    def __init__(self, memory_path=None, relationship_path=None):
        self.memory_path = memory_path or str(BASE_DIR / "data" / "memory" / "facts.json")
        self.relationship_path = relationship_path or str(BASE_DIR / "data" / "memory" / "relationship.json")
        self._lock = threading.Lock()
        self.facts = self.load_facts()
        self.relationship = self.load_relationship()

    # ---------- 事实记忆 ----------
    def load_facts(self):
        if not os.path.exists(self.memory_path):
            return {"facts": []}
        with open(self.memory_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_facts(self):
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        tmp_path = self.memory_path + ".tmp"
        with self._lock:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.facts, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.memory_path)

    # ---------- 关系状态 ----------
    def load_relationship(self):
        if not os.path.exists(self.relationship_path):
            return {
                "closeness": 10,
                "last_interaction": None,
                "overall_mood": "neutral"
            }
        with open(self.relationship_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_relationship(self):
        os.makedirs(os.path.dirname(self.relationship_path), exist_ok=True)
        tmp_path = self.relationship_path + ".tmp"
        with self._lock:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.relationship, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.relationship_path)

    def update_relationship(self, closeness_delta=0, mood=None):
        """根据互动情况更新关系状态"""
        self.relationship["closeness"] = max(0, min(100, self.relationship["closeness"] + closeness_delta))
        if mood:
            self.relationship["overall_mood"] = mood
        self.relationship["last_interaction"] = time.time()
        self.save_relationship()

    def get_relationship_context(self):
        """返回给 LLM 的关系背景描述，但不给出具体行为指令"""
        closeness = self.relationship.get("closeness", 10)
        mood = self.relationship.get("overall_mood", "neutral")
        last = self.relationship.get("last_interaction")
        if last:
            days = (time.time() - last) / 86400
            last_text = f"上次互动是 {days:.1f} 天前"
        else:
            last_text = "你们还不太熟"

        return f"目前亲密度：{closeness}/100。{last_text}。整体情绪倾向：{mood}。"

    # ---------- 遗忘曲线 ----------
    def calculate_retention(self, fact):
        importance_factor = {1: 0.5, 2: 0.7, 3: 1.0, 4: 1.5, 5: 2.0}
        base_speed = 10.0
        speed = base_speed / importance_factor[fact.get("importance", 3)]

        now = time.time()
        last_reviewed = fact.get("last_reviewed_at", now)
        days = (now - last_reviewed) / 86400.0

        review_count = fact.get("review_count", 0)
        review_bonus = 1 + review_count * 0.2
        effective_speed = speed * review_bonus

        return math.exp(-days / effective_speed)

    # ---------- 记忆注入 ----------
    def get_memory_injection(self, limit=5):
        clear_memories = []
        vague_memories = []
        flashback_memory = None

        if not self.facts["facts"]:
            return clear_memories, vague_memories, flashback_memory

        reviewed = False
        for fact in self.facts["facts"]:
            if fact.get("subject") != "user":
                continue

            retention = self.calculate_retention(fact)

            fact_text = fact["text"]
            if fact_text.startswith("用户"):
                fact_text = "主人" + fact_text[len("用户"):]

            if retention > 0.7:
                clear_memories.append(fact_text)
                fact["last_reviewed_at"] = time.time()
                reviewed = True
            elif retention > 0.3:
                keyword = fact_text[:6] + "..."
                vague_memories.append(f"主人好像和“{keyword}”有关，但记不太清了")
            else:
                if random.random() < 0.05:
                    flashback_memory = fact_text

        if reviewed:
            self.save_facts()

        clear_memories = clear_memories[:limit]
        vague_memories = vague_memories[:limit]

        return clear_memories, vague_memories, flashback_memory

    # ---------- 添加/更新事实 ----------
    def add_or_update_fact(self, text, importance=3, emotion_tag="neutral", subject="user"):
        now = time.time()
        for fact in self.facts["facts"]:
            if fact["text"] == text and fact.get("subject") == subject:
                fact["importance"] = max(fact["importance"], importance)
                fact["emotion_tag"] = emotion_tag
                fact["last_reviewed_at"] = now
                fact["review_count"] += 1
                self.save_facts()
                return

        new_fact = {
            "id": f"f_{int(now)}",
            "text": text,
            "subject": subject,
            "importance": importance,
            "emotion_tag": emotion_tag,
            "created_at": now,
            "last_reviewed_at": now,
            "review_count": 0
        }
        self.facts["facts"].append(new_fact)
        self.save_facts()