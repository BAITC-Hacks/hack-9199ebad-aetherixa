from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import CollectionPieceType, QuestStepStatus, RatingLevel, ResponseStatus

RATING_FIELD_KEYS = [
    "context_need", "data_sources", "expected_result",
    "success_criteria", "constraints", "users", "contact_format",
]


# ---------- Task ----------

class TaskFields(BaseModel):
    """Семь полей карточки, участвующих в рейтинге. Пустая строка = не заполнено."""
    context_need: str = ""
    data_sources: str = ""
    expected_result: str = ""
    success_criteria: str = ""
    constraints: str = ""
    users: str = ""
    contact_format: str = ""


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    tag: str = Field(default="общее", min_length=1, max_length=100)
    draft_text: str = Field(default="", max_length=20000)
    fields: TaskFields = Field(default_factory=TaskFields)


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=250)
    tag: Optional[str] = Field(default=None, min_length=1, max_length=100)
    draft_text: Optional[str] = Field(default=None, max_length=20000)
    fields: Optional[TaskFields] = None


class RatingBreakdownItem(BaseModel):
    key: str
    label: str
    weight: int
    filled: bool
    confirmed: bool
    awarded_points: int


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    tag: str
    draft_text: str
    status: str
    confirmed_at: Optional[datetime]
    published_at: Optional[datetime]
    context_need: str
    data_sources: str
    expected_result: str
    success_criteria: str
    constraints: str
    users: str
    contact_format: str
    score: int
    level: RatingLevel
    selected_team_id: Optional[int]
    selected_team_name: Optional[str]
    boss_completed: bool
    created_at: datetime


class PublishIn(BaseModel):
    confirmed: Literal[True]


class TaskRatingOut(BaseModel):
    score: int
    level: RatingLevel
    missing_fields: list[str]
    breakdown: list[RatingBreakdownItem]


# ---------- Responses ----------

class ResponseCreate(BaseModel):
    team_name: str = ""
    idea: str = Field(min_length=1, max_length=20000)
    plan: str = ""
    prototype_link: str = ""
    team_id: int = Field(gt=0)
    deadline_days: Optional[int] = Field(default=None, ge=1, le=3650)


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    team_id: Optional[int]
    team_name: str
    idea: str
    plan: str
    prototype_link: str
    deadline_days: Optional[int]
    status: ResponseStatus
    created_at: datetime


# ---------- Quests ----------

class QuestStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    step_order: int
    title: str
    status: QuestStepStatus
    hint_level: int
    path_choice: Optional[str]
    submission_text: str
    hints: list[str] = Field(default_factory=list)


class QuestSubmitIn(BaseModel):
    submission_text: str = Field(min_length=1, max_length=20000)


class PathChoiceIn(BaseModel):
    choice: str


# ---------- Boss ----------

class BossCriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    order_index: int
    text: str
    confirmed: bool


class BossStatusOut(BaseModel):
    criteria: list[BossCriterionOut]
    confirmed_count: int
    total: int
    completed: bool


# ---------- Team / Workshop ----------

class TeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    title: Optional[str]


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    avatar_emoji: str
    coins: int
    experience: int
    interests: str
    skills: str
    technologies: str
    members: list[TeamMemberOut] = []


class TeamMemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    title: Optional[str] = None


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    avatar_emoji: str = "🚀"
    interests: str = ""
    skills: str = ""
    technologies: str = ""
    members: list[TeamMemberCreate] = Field(default_factory=list)


class ShopItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    icon: str
    cost: int
    category: str


class OwnedShopItemOut(BaseModel):
    item: ShopItemOut
    owned: bool
    equipped: bool


class CollectionPieceOut(BaseModel):
    type: CollectionPieceType
    unlocked: bool


# ---------- AI ----------

class AiAnalyzeIn(BaseModel):
    draft_text: str = Field(min_length=5, max_length=20000)
    task_id: Optional[int] = Field(default=None, gt=0)


class AiQuestion(BaseModel):
    field: str
    question: str


class AiAnalyzeOut(BaseModel):
    ai_used: bool
    task_id: int
    fallback_reason: Optional[str] = None
    covered_fields: list[str]
    missing_fields: list[str]
    questions: list[AiQuestion]


class AiAnswer(BaseModel):
    field: str
    question: str = Field(max_length=2000)
    answer: str = Field(max_length=20000)


class AiAssembleIn(BaseModel):
    task_id: Optional[int] = Field(default=None, gt=0)
    draft_text: str = Field(min_length=5, max_length=20000)
    answers: list[AiAnswer]


class AiAssembleOut(BaseModel):
    ai_used: bool
    task_id: int
    fallback_reason: Optional[str] = None
    title: str
    fields: TaskFields
