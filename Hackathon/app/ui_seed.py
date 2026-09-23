from sqlalchemy.orm import Session

from app.ui_models import UIPlacementMode, TaskUIPlacement


def seed_ui_modes(db: Session) -> None:
    modes = [
        ("list", "Список задач", "Каталог карточек с сортировкой и фильтрами."),
        ("top_down_houses", "Город задач", "Вид сверху с 2D-домами для задач."),
    ]
    for code, name, description in modes:
        if not db.query(UIPlacementMode).filter_by(code=code).first():
            db.add(UIPlacementMode(code=code, name=name, description=description))
    db.flush()
    from app.models import Task
    for task in db.query(Task).all():
        ensure_task_placements(db, task)
    db.commit()


def ensure_task_placements(db, task):
    modes = db.query(UIPlacementMode).all()
    if not modes:
        for code, name in (("list", "Список задач"), ("top_down_houses", "Город задач")):
            db.add(UIPlacementMode(code=code, name=name, is_active=True))
        db.flush()
        modes = db.query(UIPlacementMode).all()
    for mode in modes:
        existing = db.query(TaskUIPlacement).filter_by(task_id=task.id, mode_id=mode.id).first()
        if existing:
            continue
        index = task.id - 1
        db.add(TaskUIPlacement(task_id=task.id, mode_id=mode.id, sort_order=task.id,
                              x=100 + (index % 5) * 170, y=100 + (index // 5) * 260,
                              width=120, height=110, visual_asset_key="house_default",
                              visual_config_json="{}", is_visible=True))
    db.flush()
