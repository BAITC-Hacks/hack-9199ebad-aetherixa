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
    if not AI_API_KEY or os.getenv("AI_FORCE_FALLBACK", "").lower() in ("1", "true", "yes"):
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
            result = json.loads(_strip_json_fences(text))
            return result if isinstance(result, dict) else None
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
    if _valid_analysis(result):
        return {**result, "ai_used": True, "fallback_reason": None}
    return {"ai_used": False, "fallback_reason": fallback_reason(), **_fallback_analyze(draft_text)}


def fallback_reason():
    if os.getenv("AI_FORCE_FALLBACK", "").lower() in ("1", "true", "yes"):
        return "Включён локальный разбор по правилам без обращения к AI; проверьте найденные поля."
    return "AI_API_KEY не настроен: использован локальный разбор по правилам." if not AI_API_KEY else "AI недоступен или вернул некорректный ответ: использован локальный разбор по правилам."


def _valid_analysis(result):
    if not isinstance(result, dict):
        return False
    questions = result.get("questions")
    if not isinstance(questions, list) or not 3 <= len(questions) <= 5:
        return False
    for question in questions:
        if (not isinstance(question, dict) or not isinstance(question.get("field"), str)
                or question["field"] not in FIELD_HINTS):
            return False
        if (not isinstance(question.get("question"), str) or not question["question"].strip()
                or len(question["question"]) > 2000):
            return False
    for key in ("covered_fields", "missing_fields"):
        values = result.get(key)
        if not isinstance(values, list) or any(not isinstance(value, str) or value not in FIELD_HINTS for value in values):
            return False
    return not set(result["covered_fields"]).intersection(result["missing_fields"])


FIELD_LABELS = {
    "context_need": ["Контекст и потребность", "Контекст", "Проблема", "Потребность"],
    "data_sources": ["Данные и материалы", "Источники данных", "Данные", "Материалы"],
    "expected_result": ["Ожидаемый результат", "Результат"],
    "success_criteria": ["Критерии успеха", "Критерии", "Критерий успеха"],
    "constraints": ["Ограничения", "Сроки"],
    "users": ["Пользователи", "Целевая аудитория"],
    "contact_format": ["Связь с бизнесом", "Формат связи", "Контакты", "Контакт"],
}
LABEL_KEYS = {label.casefold(): key for key, labels in FIELD_LABELS.items() for label in [key, *labels]}
LABEL_PATTERN = re.compile(r"(?<!\w)(" + "|".join(re.escape(label) for label in sorted(LABEL_KEYS, key=len, reverse=True))
                           + r")\s*[:—–]\s*", re.IGNORECASE)

# These rules recognize explicit wording only. Coverage means a source snippet
# was found, not that the task was semantically verified or is ready to publish.
FIELD_CUES = {
    "context_need": r"\b(?:сейчас|вручную|долго|очеред[ьи]|ошибки|теряют|теряем|автоматиз\w*)\b",
    "data_sources": r"\b(?:есть|имеется|имеются|доступны|доступен|предоставим|передадим)\b.{0,60}\b(?:csv|excel|xlsx|данные|таблиц\w*|файл\w*|документ\w*)\b",
    "expected_result": r"\b(?:(?:нужен|нужна|нужно|хотим|создать|разработать)\s+(?:(?:получить|создать|разработать)\s+)?(?:прототип|форм\w*|сайт|сервис|экран|приложени\w*|бот\w*)|на выходе|ожидаем(?:ый)? результат)\b",
    "success_criteria": r"\b(?:успех(?:ом)? считаем|успешно[,:]? если|принимаем[,:]? если|проверим[,:]? что|считается успешным|критери[йи] успеха)\b",
    "constraints": r"\b(?:срок\s*[-—:]?\s*\d+|за\s+\d+\s+(?:дн\w*|час\w*|недел\w*)|до\s+\d{1,2}[./]\d{1,2}|без интеграци\w*|без внешни\w*|не использовать|только локально)\b",
    "users": r"\b(?:пользоваться будут|пользователи|для (?:операторов|клиентов|администраторов|учителей|сотрудников|бариста))\b",
    "contact_format": r"\b(?:контакт|связь|обратная связь|созвон|telegram|телеграм|почта|e-mail)\b",
}


def _has_information(value: str, field: str) -> bool:
    cleaned = value.strip().casefold().replace("ё", "е")
    bare = cleaned.strip(" .;,—-?!")
    if not bare or bare in {"нет", "не знаю", "не указано", "неизвестно", "уточним", "пока нет"}:
        return False
    if re.match(r"^(?:(?:пока|еще)\s+)?(?:не знаю\b|неизвестно\b|не известно\b|не указан[оаы]?\b|не определен[оаы]?\b)", cleaned):
        return False
    if field == "data_sources" and re.search(r"\b(?:нет данных|нет материалов|нет информации|данных нет|данные отсутствуют)\b", cleaned):
        return False
    if re.match(r"^(?:данные|материалы|контакты?|сроки|критерии|пользователи)\s+(?:пока\s+)?(?:не указан[оаы]?|неизвестн[оаы]?|отсутствуют)\b", cleaned):
        return False
    return True


def _append_source(fields: dict, key: str, value: str) -> None:
    value = value.strip()
    if _has_information(value, key) and value not in fields[key].split("\n"):
        fields[key] = f"{fields[key]}\n{value}".strip()


def _extract_draft_fields(draft_text: str) -> dict:
    """Copy original labeled values or clearly signaled sentences, never invent."""
    fields = {key: "" for key in FIELD_HINTS}
    labels = list(LABEL_PATTERN.finditer(draft_text))
    for index, match in enumerate(labels):
        end = labels[index + 1].start() if index + 1 < len(labels) else len(draft_text)
        _append_source(fields, LABEL_KEYS[match.group(1).casefold()], draft_text[match.end():end])
    # Text within a labeled section belongs to that section. Only unlabelled
    # prose is classified with cues, avoiding e.g. constraints being mistaken for data.
    prose = draft_text[:labels[0].start()] if labels else draft_text
    for sentence in re.split(r"(?<=[.!?])\s+|[\n;]+", prose):
        for key, pattern in FIELD_CUES.items():
            if re.search(pattern, sentence, re.IGNORECASE):
                _append_source(fields, key, sentence)
    return fields


def _fallback_analyze(draft_text: str) -> dict:
    """Deterministic questionnaire selected from the actual source material."""
    fields = _extract_draft_fields(draft_text)
    covered = [key for key in FIELD_HINTS if fields[key]]
    missing = [key for key in FIELD_HINTS if not fields[key]]
    prompts = {
        "context_need": "Что происходит сейчас и какую проблему нужно решить?",
        "data_sources": "Какие данные, материалы или примеры вы можете предоставить?",
        "expected_result": "Какой конкретный результат должна передать команда?",
        "success_criteria": "Как вы проверите, что результат решает проблему?",
        "constraints": "Какие есть сроки, ограничения или требования к технологиям?",
        "users": "Кто будет пользоваться решением и в каком сценарии?",
        "contact_format": "Кто со стороны бизнеса даст обратную связь и как с ним связаться?",
    }
    detail_prompts = {
        "context_need": "Какой пример лучше всего показывает описанную проблему?",
        "data_sources": "Какие поля есть в указанных данных и как команда получит доступ?",
        "expected_result": "Какой основной сценарий должен поддерживать указанный результат?",
        "success_criteria": "На каких примерах и кто проверит указанный критерий?",
        "constraints": "Какие из указанных ограничений обязательны для первого прототипа?",
        "users": "Какую основную операцию выполнят указанные пользователи?",
        "contact_format": "Когда указанный контакт сможет проверить промежуточный результат?",
    }
    picks = missing[:5]
    # When nearly all fields are present, clarify the shortest (least detailed)
    # snippets instead of pretending that already provided facts are missing.
    picks += sorted(covered, key=lambda key: len(fields[key]))[:max(0, 3 - len(picks))]
    return {
        "covered_fields": covered,
        "missing_fields": missing,
        "questions": [{"field": key, "question": prompts[key] if key in missing else
                       f"Вы указали: «{fields[key][:140]}». {detail_prompts[key]}"} for key in picks],
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
    if (isinstance(result, dict) and isinstance(result.get("title"), str) and result["title"].strip()
            and len(result["title"]) <= 250
            and all(isinstance(result.get(key), str) and len(result[key]) <= 20000 for key in FIELD_HINTS)):
        fields = {key: result[key] for key in FIELD_HINTS}
        return {"ai_used": True, "fallback_reason": None, "title": result["title"], "fields": fields}
    return {"ai_used": False, "fallback_reason": fallback_reason(), **_fallback_assemble(draft_text, answers)}


def _fallback_assemble(draft_text: str, answers: list[dict]) -> dict:
    fields = _extract_draft_fields(draft_text)
    for a in answers:
        if isinstance(a.get("field"), str) and a["field"] in fields and isinstance(a.get("answer"), str):
            _append_source(fields, a["field"], a["answer"])
    return {"title": draft_text[:40], "fields": fields}
