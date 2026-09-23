"""
Формула рейтинга — в одном месте, чтобы её было легко проверить и объяснить
на демонстрации. Веса и подписи полей взяты из раздела 4 регламента кейса.
"""
from app.enums import RatingLevel
from app.models import Task

# (ключ поля, подпись, вес)
RATING_WEIGHTS: list[tuple[str, str, int]] = [
    ("context_need", "Контекст и потребность", 20),
    ("data_sources", "Данные и материалы", 20),
    ("expected_result", "Ожидаемый результат", 15),
    ("success_criteria", "Критерии успеха", 15),
    ("constraints", "Ограничения", 10),
    ("users", "Пользователи", 10),
    ("contact_format", "Связь с бизнесом", 10),
]
assert sum(w for _, _, w in RATING_WEIGHTS) == 100


def compute_rating(task: Task) -> dict:
    """Возвращает score, level, список недостающих полей и подробную раскладку баллов."""
    score = 0
    missing: list[str] = []
    breakdown = []
    for key, label, weight in RATING_WEIGHTS:
        value = (getattr(task, key) or "").strip()
        filled = len(value) > 0
        confirmed = bool(task.confirmed_at)
        if filled and confirmed:
            score += weight
        if not filled:
            missing.append(label)
        breakdown.append({"key": key, "label": label, "weight": weight, "filled": filled,
                          "confirmed": confirmed and filled, "awarded_points": weight if filled and confirmed else 0})
    level = RatingLevel.from_score(score)
    return {"score": score, "level": level, "missing_fields": missing, "breakdown": breakdown}


def apply_rating(task: Task) -> None:
    """Пересчитывает и записывает score/level прямо в объект задачи перед сохранением."""
    result = compute_rating(task)
    task.score = result["score"]
    task.level = result["level"]
