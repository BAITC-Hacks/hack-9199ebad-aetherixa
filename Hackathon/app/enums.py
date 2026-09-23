import enum


class RatingLevel(str, enum.Enum):
    """Уровни готовности задачи. Границы — из регламента кейса (раздел 4)."""
    draft = "draft"        # 0-39: черновик
    working = "working"    # 40-69: рабочая
    ready = "ready"        # 70-89: готовая
    priority = "priority"  # 90-100: приоритетная

    @staticmethod
    def from_score(score: int) -> "RatingLevel":
        if score >= 90:
            return RatingLevel.priority
        if score >= 70:
            return RatingLevel.ready
        if score >= 40:
            return RatingLevel.working
        return RatingLevel.draft


class ResponseStatus(str, enum.Enum):
    pending = "pending"    # на рассмотрении
    selected = "selected"  # выбрана бизнесом
    rejected = "rejected"  # отклонена


class QuestStepStatus(str, enum.Enum):
    locked = "locked"    # ещё не открыт
    current = "current"  # выполняется сейчас
    review = "review"    # отправлен результат, ждёт подтверждения
    done = "done"         # подтверждён


class CollectionPieceType(str, enum.Enum):
    research = "research"          # Исследование
    plan = "plan"                  # План
    prototype = "prototype"        # Прототип
    verification = "verification"  # Проверка
    result = "result"              # Результат
