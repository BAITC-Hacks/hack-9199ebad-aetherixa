from __future__ import annotations

from dataclasses import replace
from threading import Lock

from flask import Flask, abort, jsonify, render_template

from models import (
    BUILDINGS,
    COLLECTION,
    CRITERIA,
    HINT_LABELS,
    MISSION,
    MISSIONS,
    SHOP_ITEMS,
    serialize,
)

app = Flask(__name__)

_state_lock = Lock()
_criterion_state = {criterion.id: criterion.confirmed for criterion in CRITERIA}
_hint_state = {step.id: 0 for mission in MISSIONS.values() for step in mission.steps if step.supports_hints}


def current_criteria():
    return tuple(replace(item, confirmed=_criterion_state[item.id]) for item in CRITERIA)


@app.get("/")
def index():
    criteria = current_criteria()
    initial_data = {
        "buildings": [serialize(item) for item in BUILDINGS],
        "hints": list(MISSION.hints),
        "hint_labels": list(HINT_LABELS),
    }
    return render_template(
        "index.html",
        buildings=BUILDINGS,
        mission=MISSION,
        shop_items=SHOP_ITEMS,
        collection=COLLECTION,
        criteria=criteria,
        confirmed_count=sum(item.confirmed for item in criteria),
        initial_data=initial_data,
    )


@app.get("/api/buildings")
def api_buildings():
    return jsonify([serialize(item) for item in BUILDINGS])


@app.get("/api/missions/<mission_id>")
def api_mission(mission_id: str):
    mission = MISSIONS.get(mission_id)
    if mission is None:
        abort(404, description="Mission not found")
    return jsonify(serialize(mission))


@app.post("/api/criteria/<criterion_id>/toggle")
def api_toggle_criterion(criterion_id: str):
    if criterion_id not in _criterion_state:
        abort(404, description="Criterion not found")
    with _state_lock:
        _criterion_state[criterion_id] = not _criterion_state[criterion_id]
        confirmed = _criterion_state[criterion_id]
        confirmed_count = sum(_criterion_state.values())
    return jsonify(
        id=criterion_id,
        confirmed=confirmed,
        confirmed_count=confirmed_count,
        total=len(_criterion_state),
        complete=confirmed_count == len(_criterion_state),
    )


@app.post("/api/hints/<step_id>/next")
def api_next_hint(step_id: str):
    if step_id not in _hint_state:
        abort(404, description="Hint-enabled step not found")
    with _state_lock:
        level = _hint_state[step_id]
        if level < len(MISSION.hints):
            hint = MISSION.hints[level]
            level += 1
            _hint_state[step_id] = level
        else:
            hint = None
    return jsonify(
        step_id=step_id,
        level=level,
        hint=hint,
        label=HINT_LABELS[min(level, len(HINT_LABELS) - 1)],
        exhausted=level >= len(MISSION.hints),
    )


if __name__ == "__main__":
    app.run(debug=True)

