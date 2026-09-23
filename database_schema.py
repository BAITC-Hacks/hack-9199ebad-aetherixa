from __future__ import annotations

import os
import urllib
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


# =========================
# Подключение к SQL Server
# =========================

def make_engine():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        params = urllib.parse.quote_plus(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=DESKTOP-D5H3SMJ\\SQLEXPRESS;"
            "DATABASE=aetherix_db;"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

        database_url = (
            f"mssql+pyodbc:///?odbc_connect={params}"
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        future=True,
    )


engine = make_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


# =========================
# Базовый класс моделей
# =========================

class Base(DeclarativeBase):
    pass


# =========================
# Пользователи
# =========================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    # business или student
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    business_profile: Mapped[
        "BusinessProfile | None"
    ] = relationship(
        back_populates="user",
        uselist=False,
    )

    team_membership: Mapped[
        "TeamMember | None"
    ] = relationship(
        back_populates="user",
        uselist=False,
    )


# =========================
# Бизнес-профиль
# =========================

class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )

    company_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    industry: Mapped[str | None] = mapped_column(
        String(100),
    )

    contact_format: Mapped[str | None] = mapped_column(
        String(100),
    )

    user: Mapped[User] = relationship(
        back_populates="business_profile",
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="business",
    )


# =========================
# Команды студентов
# =========================

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
    )

    interests: Mapped[str | None] = mapped_column(
        Text,
    )

    skills: Mapped[str | None] = mapped_column(
        Text,
    )

    technologies: Mapped[str | None] = mapped_column(
        Text,
    )

    members: Mapped[list["TeamMember"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
    )

    proposals: Mapped[list["Proposal"]] = relationship(
        back_populates="team",
    )


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )

    team: Mapped[Team] = relationship(
        back_populates="members",
    )

    user: Mapped[User] = relationship(
        back_populates="team_membership",
    )


# =========================
# Бизнес-задача
# =========================

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    business_id: Mapped[int] = mapped_column(
        ForeignKey("business_profiles.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    raw_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    context_need: Mapped[str | None] = mapped_column(
        Text,
    )

    data_materials: Mapped[str | None] = mapped_column(
        Text,
    )

    expected_result: Mapped[str | None] = mapped_column(
        Text,
    )

    success_criteria: Mapped[str | None] = mapped_column(
        Text,
    )

    constraints: Mapped[str | None] = mapped_column(
        Text,
    )

    users_description: Mapped[str | None] = mapped_column(
        Text,
    )

    business_connection: Mapped[str | None] = mapped_column(
        Text,
    )

    industry: Mapped[str | None] = mapped_column(
        String(100),
    )

    # draft, published, closed
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False,
    )

    readiness_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # draft, working, ready, priority
    readiness_level: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False,
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    business: Mapped[BusinessProfile] = relationship(
        back_populates="tasks",
    )

    questions: Mapped[list["ClarifyingQuestion"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )

    score_items: Mapped[list["TaskScoreItem"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )

    proposals: Mapped[list["Proposal"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )

    ui_placements: Mapped[list["TaskUIPlacement"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


# =========================
# AI-вопросы
# =========================

class ClarifyingQuestion(Base):
    __tablename__ = "clarifying_questions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False,
    )

    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    answer_text: Mapped[str | None] = mapped_column(
        Text,
    )

    generated_by_ai: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    confirmed_by_business: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    task: Mapped[Task] = relationship(
        back_populates="questions",
    )


# =========================
# Баллы по каждому критерию
# =========================

class TaskScoreItem(Base):
    __tablename__ = "task_score_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False,
    )

    criterion_code: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    criterion_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    max_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    awarded_points: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
    )

    task: Mapped[Task] = relationship(
        back_populates="score_items",
    )

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "criterion_code",
        ),
    )


# =========================
# Справочник критериев рейтинга
# =========================

class RatingCriterion(Base):
    __tablename__ = "rating_criteria"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    code: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    max_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )


# =========================
# Отклики команд
# =========================

class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )

    idea: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    plan: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    deadline_days: Mapped[int | None] = mapped_column(
        Integer,
    )

    prototype_url: Mapped[str | None] = mapped_column(
        String(500),
    )

    # submitted, selected, rejected
    status: Mapped[str] = mapped_column(
        String(20),
        default="submitted",
        nullable=False,
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    task: Mapped[Task] = relationship(
        back_populates="proposals",
    )

    team: Mapped[Team] = relationship(
        back_populates="proposals",
    )


# =========================
# Режимы отображения UI
# =========================

class UIPlacementMode(Base):
    __tablename__ = "ui_placement_modes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    placements: Mapped[list["TaskUIPlacement"]] = relationship(
        back_populates="mode",
    )


# =========================
# Размещение задачи в UI
# =========================

class TaskUIPlacement(Base):
    __tablename__ = "task_ui_placements"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False,
    )

    mode_id: Mapped[int] = mapped_column(
        ForeignKey("ui_placement_modes.id"),
        nullable=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Координаты для режима города/домов
    x: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
    )

    y: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
    )

    width: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
    )

    height: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
    )

    # Например: house_blue, house_red, house_priority
    visual_asset_key: Mapped[str | None] = mapped_column(
        String(200),
    )

    # Дополнительные настройки отображения в JSON
    visual_config_json: Mapped[str | None] = mapped_column(
        Text,
    )

    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    task: Mapped[Task] = relationship(
        back_populates="ui_placements",
    )

    mode: Mapped[UIPlacementMode] = relationship(
        back_populates="placements",
    )

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "mode_id",
        ),
    )


# =========================
# Начальные справочные данные
# =========================

def seed_reference_data(session):
    ui_modes = [
        (
            "list",
            "Список задач",
            "Каталог карточек с сортировкой по рейтингу и фильтрами.",
        ),
        (
            "top_down_houses",
            "Город задач",
            "Вид сверху: каждая задача представлена 2D-домом.",
        ),
    ]

    for code, name, description in ui_modes:
        exists = (
            session.query(UIPlacementMode)
            .filter_by(code=code)
            .first()
        )

        if not exists:
            session.add(
                UIPlacementMode(
                    code=code,
                    name=name,
                    description=description,
                )
            )

    rating_criteria = [
        (
            "context_need",
            "Контекст и потребность",
            20,
            "Понятно, что происходит сейчас и что необходимо изменить.",
        ),
        (
            "data_materials",
            "Данные и материалы",
            20,
            "Указаны доступные данные, примеры или источники.",
        ),
        (
            "expected_result",
            "Ожидаемый результат",
            15,
            "Описан конкретный результат работы команды.",
        ),
        (
            "success_criteria",
            "Критерии успеха",
            15,
            "Есть измеримые признаки принятия решения.",
        ),
        (
            "constraints",
            "Ограничения",
            10,
            "Указаны сроки, технологии, доступы или другие ограничения.",
        ),
        (
            "users_description",
            "Пользователи",
            10,
            "Понятно, для кого создаётся решение.",
        ),
        (
            "business_connection",
            "Связь с бизнесом",
            10,
            "Есть контакт и формат обратной связи.",
        ),
    ]

    for code, name, max_points, description in rating_criteria:
        exists = (
            session.query(RatingCriterion)
            .filter_by(code=code)
            .first()
        )

        if not exists:
            session.add(
                RatingCriterion(
                    code=code,
                    name=name,
                    max_points=max_points,
                    description=description,
                )
            )


# =========================
# Создание базы
# =========================

def init_db():
    Base.metadata.create_all(bind=engine)

    with SessionLocal.begin() as session:
        seed_reference_data(session)

    print("Таблицы созданы.")
    print("Справочники рейтинга и UI добавлены.")


if __name__ == "__main__":
    init_db()