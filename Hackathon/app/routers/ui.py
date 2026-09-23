import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task
from app.ui_models import TaskUIPlacement, UIPlacementMode
from app.ui_seed import ensure_task_placements

router = APIRouter(prefix="/api/ui", tags=["ui"])


class PlacementIn(BaseModel):
    x: float | None = Field(default=None, ge=-1000000, le=1000000)
    y: float | None = Field(default=None, ge=-1000000, le=1000000)
    width: float | None = Field(default=None, gt=0, le=10000)
    height: float | None = Field(default=None, gt=0, le=10000)
    sort_order: int | None = None
    visual_asset_key: str | None = Field(default=None, max_length=200)
    visual_config: dict | None = None
    is_visible: bool | None = None


def _out(item):
    try:
        config = json.loads(item.visual_config_json or "{}")
        if not isinstance(config, dict):
            config = {}
    except (ValueError, TypeError):
        config = {}
    return {"task_id": item.task_id, "mode": item.mode.code, "x": item.x, "y": item.y,
            "width": item.width, "height": item.height, "sort_order": item.sort_order,
            "visual_asset_key": item.visual_asset_key, "visual_config": config,
            "is_visible": item.is_visible}


@router.get("/placements")
def list_placements(mode: Literal["list", "top_down_houses"] = "top_down_houses",
                    task_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(TaskUIPlacement).join(UIPlacementMode).join(Task).filter(UIPlacementMode.code == mode)
    query = query.filter(Task.id == task_id) if task_id else query.filter(Task.status == "published")
    return [_out(item) for item in query.order_by(TaskUIPlacement.sort_order).all()]


@router.put("/placements/{task_id}/{mode}")
def update_placement(task_id: int, mode: Literal["list", "top_down_houses"], payload: PlacementIn,
                     db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Задача не найдена")
    ensure_task_placements(db, task)
    item = db.query(TaskUIPlacement).join(UIPlacementMode).filter(TaskUIPlacement.task_id == task_id, UIPlacementMode.code == mode).one()
    for key, value in payload.model_dump(exclude_none=True).items():
        if key == "visual_config":
            item.visual_config_json = json.dumps(value, ensure_ascii=False)
        else:
            setattr(item, key, value)
    db.commit()
    return _out(item)
