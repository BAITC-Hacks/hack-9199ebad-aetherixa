"""
Две AI-функции кейса (раздел 5):
  1. analyze_draft   — анализ полноты черновика + генерация уточняющих вопросов
  2. assemble_card   — сборка карточки строго из черновика и ответов пользователя

Если AI_API_KEY не задан или внешний вызов не удался — используется
локальная заглушка (это прямо разрешено регламентом кейса), при этом
вызывающий код всегда знает, каким способом получен результат (ai_used).
"""
import json
import os
import re

import httpx

from app.rating import RATING_WEIGHTS

AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.anthropic.com/v1/messages")
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-6")

FIELD_HINTS = {key: label for key, label, _ in RATING_WEIGHTS}


def _strip_json_fences(text: str) -> str:
    return re.sub(r"```json|```", "", text).strip()


async def _call_model(system_prompt: str, user_content: str) -> dict | None:
    """Общий вызов внешнего API. Возвращает распарсенный JSON или None при любой ошибке."""
    if not AI_API_KEY:
        return None
    headers = {
        "x-api-key": AI_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": AI_MODEL,
        "max_tokens": 1000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }
    for _attempt in range(2):  # один повтор при невалидном JSON
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(AI_BASE_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            text = "".join(
                block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
            )
            return json.loads(_strip_json_fences(text))
        except Exception:
            continue
    return None


# ---------- Функция 1: анализ полноты + вопросы ----------

ANALYZE_SYSTEM_PROMPT = """Ты помогаешь представителю бизнеса точнее описать задачу для студенческой команды.
Поля карточки: context_need, data_sources, expected_result, success_criteria, constraints, users, contact_format.
Определи, какие поля уже покрыты текстом черновика (даже частично), а какие отсутствуют.
Сформулируй от 3 до 5 уточняющих вопросов ТОЛЬКО по отсутствующим или слабо раскрытым полям.
Никогда не добавляй факты, которых нет в тексте, — только вопросы.
Верни ТОЛЬКО JSON без пояснений и без markdown-разметки:
{"covered_fields": ["..."], "missing_fields": ["..."], "questions": [{"field": "...", "question": "..."}]}"""


async def analyze_draft(draft_text: str) -> dict:
    result = await _call_model(ANALYZE_SYSTEM_PROMPT, f'Черновик: """{draft_text}"""')
    if result and isinstance(result.get("questions"), list) and result["questions"]:
        return {"ai_used": True, **result}
    return {"ai_used": False, **_fallback_analyze(draft_text)}


def _fallback_analyze(draft_text: str) -> dict:
    """Простая эвристика: считаем поле покрытым, если в тексте есть однокоренное слово."""
    lowered = draft_text.lower()
    missing_keys = [key for key in FIELD_HINTS if key.split("_")[0] not in lowered]
    if not missing_keys:
        missing_keys = list(FIELD_HINTS.keys())
    picks = missing_keys[:4]
    covered = [FIELD_HINTS[k] for k in FIELD_HINTS if k not in picks]
    return {
        "covered_fields": covered,
        "missing_fields": [FIELD_HINTS[k] for k in picks],
        "questions": [{"field": k, "question": f"Уточните: {FIELD_HINTS[k].lower()}?"} for k in picks],
    }


# ---------- Функция 2: сборка карточки ----------

ASSEMBLE_SYSTEM_PROMPT = """Собери карточку бизнес-задачи строго из предоставленных материалов: черновика и ответов
пользователя на уточняющие вопросы. Используй ТОЛЬКО то, что явно сказано. Если по какому-то полю
информации всё ещё недостаточно — верни для него пустую строку, не домысливай и не обобщай сверх сказанного.
Не добавляй никаких чисел, сроков, технологий или критериев, которых не было в исходном тексте.
Верни ТОЛЬКО JSON:
{"title": "...", "context_need": "...", "data_sources": "...", "expected_result": "...",
 "success_criteria": "...", "constraints": "...", "users": "...", "contact_format": "..."}"""


async def assemble_card(draft_text: str, answers: list[dict]) -> dict:
    qa_text = "\n".join(f"- {a['question']} → {a['answer']}" for a in answers)
    user_content = f'Черновик: """{draft_text}"""\nОтветы на вопросы:\n{qa_text}'
    result = await _call_model(ASSEMBLE_SYSTEM_PROMPT, user_content)
    if result and isinstance(result, dict):
        fields = {key: result.get(key, "") or "" for key, _, _ in RATING_WEIGHTS}
        return {"ai_used": True, "title": result.get("title", "") or draft_text[:40], "fields": fields}
    return {"ai_used": False, **_fallback_assemble(draft_text, answers)}


def _fallback_assemble(draft_text: str, answers: list[dict]) -> dict:
    fields = {key: "" for key, _, _ in RATING_WEIGHTS}
    combined = draft_text + " " + " ".join(a["answer"] for a in answers if a.get("answer"))
    fields["context_need"] = combined.strip()[:300]
    for a in answers:
        if a.get("field") in fields and a.get("answer"):
            fields[a["field"]] = a["answer"]
    return {"title": draft_text[:40], "fields": fields}
