"""Run: python -m unittest discover -s tests -v. No network or real SQL Server."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

_temp = tempfile.TemporaryDirectory(prefix="ai_sana_integration_")
_db_path = Path(_temp.name) / "integration.sqlite3"
os.environ["DATABASE_URL"] = "sqlite:///" + _db_path.as_posix()
os.environ["SEED_DEMO"] = "false"
os.environ["AI_API_KEY"] = ""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.main import app
from app.database import SessionLocal, engine
from app import ai_service, models

FIELDS = {
    "context_need": "Заявки поддержки разбираются вручную.",
    "data_sources": "Обезличенный CSV с обращениями за месяц.",
    "expected_result": "Рабочая форма классификации обращений.",
    "success_criteria": "На десяти примерах сохраняется заявка и назначается категория.",
    "constraints": "Локальный прототип без передачи персональных данных.",
    "users": "Операторы службы поддержки.",
    "contact_format": "Обратная связь руководителя в чате команды.",
}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        engine.dispose()
        _db_path.unlink(missing_ok=True)
        # Never call the real model, even if an API key is present in .env.
        self.ai_patch = patch.object(ai_service, "_call_model", new=AsyncMock(return_value=None))
        self.ai_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.ai_patch.stop()
        engine.dispose()

    def request(self, method, path, expected=200, **kwargs):
        response = self.client.request(method, path, **kwargs)
        self.assertEqual(response.status_code, expected, response.text)
        return response.json() if response.content else None

    def task(self, title="Поддержка клиентов", fields=None, publish=False):
        task = self.request("POST", "/api/tasks", 201, json={
            "title": title, "tag": "поддержка", "draft_text": "Нужно ускорить обработку обращений.",
            "fields": fields if fields is not None else FIELDS,
        })
        if publish:
            task = self.request("POST", f"/api/tasks/{task['id']}/publish", json={"confirmed": True})
        return task

    def team(self, name="Исследователи"):
        return self.request("POST", "/api/teams", 201, json={
            "name": name, "avatar_emoji": "🚀", "interests": "Поддержка бизнеса",
            "skills": "Анализ данных", "technologies": "Python, SQL",
            "members": [{"name": "Алина", "title": "Разработчик"}],
        })

    def propose(self, task_id, team_id):
        return self.request("POST", f"/api/tasks/{task_id}/responses", 201, json={
            "team_id": team_id, "idea": "Сделаем классификатор обращений.",
            "plan": "Разбор данных, прототип, проверка.", "deadline_days": 3,
            "prototype_link": "https://example.com/prototype",
        })

    def selected_task(self):
        task, team = self.task(publish=True), self.team()
        response = self.propose(task["id"], team["id"])
        self.request("PATCH", f"/api/responses/{response['id']}/select")
        return task, team

    def submit(self, task_id, step_id):
        return self.request("POST", f"/api/tasks/{task_id}/quests/{step_id}/submit",
                            json={"submission_text": "Результат выполнен: проверен сценарий на трёх примерах."})

    def test_site_health_and_assets_served_by_backend(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("AI Sana", response.text)
        self.assertNotIn("{{", response.text, "Unrendered Flask expressions must not reach the browser")
        for path in ("/static/css/style.css", "/static/js/app.js", "/openapi.json", "/docs"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.request("GET", "/health")["status"], "ok")

    def test_draft_requires_confirmation_for_score_and_publication(self):
        task = self.task()
        self.assertEqual(task["status"], "draft")
        self.assertEqual(task["score"], 0)
        self.assertIsNone(task["confirmed_at"])
        self.assertEqual(self.request("GET", "/api/tasks"), [])
        self.assertEqual([row["id"] for row in self.request("GET", "/api/tasks?status=draft")], [task["id"]])
        invalid = self.client.post(f"/api/tasks/{task['id']}/publish", json={"confirmed": False})
        self.assertIn(invalid.status_code, (400, 422))
        published = self.request("POST", f"/api/tasks/{task['id']}/publish", json={"confirmed": True})
        self.assertEqual(published["status"], "published")
        self.assertEqual(published["score"], 100)
        self.assertEqual(published["level"], "priority")
        self.assertIsNotNone(published["confirmed_at"])
        rating = self.request("GET", f"/api/tasks/{task['id']}/rating")
        self.assertEqual(rating["score"], 100)
        self.assertEqual(rating["missing_fields"], [])
        self.assertEqual(sum(item["weight"] for item in rating["breakdown"]), 100)

    def test_edit_invalidates_confirmation_preserving_unedited_fields(self):
        task = self.task(publish=True)
        changed = self.request("PATCH", f"/api/tasks/{task['id']}", json={
            "fields": {"expected_result": "Новая форма обработки обращений"},
        })
        self.assertEqual(changed["expected_result"], "Новая форма обработки обращений")
        self.assertEqual(changed["data_sources"], FIELDS["data_sources"])
        self.assertEqual(changed["score"], 0)
        self.assertEqual(changed["status"], "draft")
        self.assertIsNone(changed["confirmed_at"])
        self.assertEqual(self.request("GET", "/api/tasks"), [])
        changed = self.request("POST", f"/api/tasks/{task['id']}/publish", json={"confirmed": True})
        self.assertEqual(changed["score"], 100)

    def test_ai_questions_answers_and_card_persist(self):
        task = self.task(fields={})
        draft = "Нужно сократить время обработки обращений клиентов."
        analyzed = self.request("POST", "/api/ai/analyze", json={"task_id": task["id"], "draft_text": draft})
        self.assertFalse(analyzed["ai_used"])
        self.assertTrue(analyzed.get("fallback_reason"))
        self.assertGreaterEqual(len(analyzed["questions"]), 3)
        self.assertLessEqual(len(analyzed["questions"]), 5)
        self.assertTrue(all(q["field"] in FIELDS for q in analyzed["questions"]))
        questions = self.request("GET", f"/api/tasks/{task['id']}/questions")
        self.assertEqual(len(questions), len(analyzed["questions"]))
        answers = [{**q, "answer": FIELDS[q["field"]]} for q in analyzed["questions"]]
        assembled = self.request("POST", "/api/ai/assemble", json={
            "task_id": task["id"], "draft_text": draft, "answers": answers,
        })
        self.assertEqual(assembled["task_id"], task["id"])
        self.assertFalse(assembled["ai_used"])
        for answer in answers:
            self.assertEqual(assembled["fields"][answer["field"]], answer["answer"])
        engine.dispose()
        saved = self.request("GET", f"/api/tasks/{task['id']}")
        self.assertEqual(saved["score"], 0)
        self.assertEqual(saved["status"], "draft")
        saved_questions = str(self.request("GET", f"/api/tasks/{task['id']}/questions"))
        for answer in answers:
            self.assertIn(answer["answer"], saved_questions)

    def test_malformed_ai_results_use_safe_fallback(self):
        malformed = [
            ["not-an-object"], {"questions": [{"field": "invented", "question": 17}]},
            {"covered_fields": [], "missing_fields": [], "questions": []},
        ]
        for field in ([], {}):
            malformed.append({"covered_fields": [], "missing_fields": [],
                              "questions": [{"field": field, "question": "Что нужно сделать?"}] * 3})
        for result in malformed:
            with self.subTest(result=result), patch.object(ai_service, "_call_model", new=AsyncMock(return_value=result)):
                analyzed = self.request("POST", "/api/ai/analyze", json={"draft_text": "Нужно улучшить поддержку клиентов."})
                self.assertFalse(analyzed["ai_used"])
                self.assertGreaterEqual(len(analyzed["questions"]), 3)
        with patch.object(ai_service, "_call_model", new=AsyncMock(return_value={"title": [], "context_need": 123})):
            assembled = self.request("POST", "/api/ai/assemble", json={"draft_text": "Нужно улучшить поддержку клиентов.", "answers": []})
            self.assertFalse(assembled["ai_used"])
            self.assertTrue(all(isinstance(value, str) for value in assembled["fields"].values()))

    def test_valid_model_result_is_saved_but_never_auto_published(self):
        raw_analysis = {"covered_fields": ["context_need"],
                        "missing_fields": [key for key in FIELDS if key != "context_need"],
                        "questions": [{"field": key, "question": "Уточните " + key}
                                      for key in ("data_sources", "expected_result", "success_criteria")]}
        with patch.object(ai_service, "_call_model", new=AsyncMock(return_value=raw_analysis)):
            analyzed = self.request("POST", "/api/ai/analyze", json={"draft_text": "Нужно улучшить поддержку клиентов."})
        self.assertTrue(analyzed["ai_used"])
        task_id = analyzed["task_id"]
        self.assertTrue(all(q["ai_used"] for q in self.request("GET", f"/api/tasks/{task_id}/questions")))
        with patch.object(ai_service, "_call_model", new=AsyncMock(return_value={"title": "Карточка AI", **FIELDS})):
            assembled = self.request("POST", "/api/ai/assemble", json={
                "task_id": task_id, "draft_text": "Нужно улучшить поддержку клиентов.", "answers": [],
            })
        self.assertTrue(assembled["ai_used"])
        self.assertIsNone(assembled["fallback_reason"])
        saved = self.request("GET", f"/api/tasks/{task_id}")
        self.assertEqual(saved["title"], "Карточка AI")
        self.assertEqual(saved["score"], 0)
        self.assertEqual(saved["status"], "draft")
        self.assertEqual(self.request("GET", "/api/tasks"), [])

    def test_multiple_proposals_require_manual_selection_and_independent_rejection(self):
        task = self.task(publish=True)
        first_team, second_team = self.team("Первая команда"), self.team("Вторая команда")
        first, second = self.propose(task["id"], first_team["id"]), self.propose(task["id"], second_team["id"])
        self.assertEqual(first["deadline_days"], 3)
        self.assertIsNone(self.request("GET", f"/api/tasks/{task['id']}")["selected_team_id"])
        self.request("PATCH", f"/api/responses/{first['id']}/select")
        self.assertEqual(self.request("GET", f"/api/tasks/{task['id']}")["selected_team_id"], first_team["id"])
        self.request("PATCH", f"/api/responses/{second['id']}/select")
        responses = self.request("GET", f"/api/tasks/{task['id']}/responses")
        self.assertEqual(sum(row["status"] == "selected" for row in responses), 2)
        self.request("PATCH", f"/api/responses/{second['id']}/reject")
        responses = self.request("GET", f"/api/tasks/{task['id']}/responses")
        self.assertEqual(next(row["status"] for row in responses if row["id"] == first["id"]), "selected")
        self.assertEqual(next(row["status"] for row in responses if row["id"] == second["id"]), "rejected")
        self.assertEqual(self.request("GET", f"/api/tasks/{task['id']}")["selected_team_id"], first_team["id"])
        self.request("PATCH", f"/api/responses/{first['id']}/reject")
        self.assertIsNone(self.request("GET", f"/api/tasks/{task['id']}")["selected_team_id"])

    def test_proposals_reject_missing_team_and_draft(self):
        task, team = self.task(), self.team()
        payload = {"team_id": team["id"], "idea": "Прототип", "plan": "Проверим на примерах", "deadline_days": 2}
        response = self.client.post(f"/api/tasks/{task['id']}/responses", json=payload)
        self.assertIn(response.status_code, (400, 409))
        self.request("POST", f"/api/tasks/{task['id']}/publish", json={"confirmed": True})
        payload["team_id"] = 999999
        response = self.client.post(f"/api/tasks/{task['id']}/responses", json=payload)
        self.assertIn(response.status_code, (400, 404, 422))

    def test_catalog_sort_filters_and_team_profile_persistence(self):
        low = self.task("Минимальная задача", fields={"context_need": FIELDS["context_need"]}, publish=True)
        high = self.task("Полная задача", publish=True)
        self.assertEqual([r["id"] for r in self.request("GET", "/api/tasks?sort=rating")], [high["id"], low["id"]])
        self.assertEqual([r["id"] for r in self.request("GET", "/api/tasks?level=priority")], [high["id"]])
        self.assertEqual(self.request("GET", "/api/tasks?tag=неизвестная"), [])
        team = self.team()
        engine.dispose()
        restored = self.request("GET", f"/api/teams/{team['id']}")
        self.assertEqual(restored["interests"], "Поддержка бизнеса")
        self.assertEqual(restored["members"][0]["name"], "Алина")

    def test_ui_layouts_persist_separately_and_reject_invalid_dimensions(self):
        task = self.task(publish=True)
        for mode in ("list", "top_down_houses"):
            placements = self.request("GET", f"/api/ui/placements?mode={mode}&task_id={task['id']}")
            self.assertEqual(len(placements), 1)
            self.assertEqual(placements[0]["task_id"], task["id"])
        updated = self.request("PUT", f"/api/ui/placements/{task['id']}/top_down_houses", json={
            "x": 145.5, "y": 90.25, "width": 64, "height": 72,
            "visual_asset_key": "house_blue", "visual_config": {"color": "#123456", "label": "Дом задачи"},
        })
        self.assertEqual(float(updated["x"]), 145.5)
        engine.dispose()
        restored = self.request("GET", f"/api/ui/placements?mode=top_down_houses&task_id={task['id']}")[0]
        self.assertEqual(float(restored["y"]), 90.25)
        self.assertEqual(restored["visual_config"]["label"], "Дом задачи")
        self.assertEqual(restored["visual_asset_key"], "house_blue")
        listing = self.request("GET", f"/api/ui/placements?mode=list&task_id={task['id']}")[0]
        self.assertNotEqual(listing["visual_config"], restored["visual_config"])
        response = self.client.put(f"/api/ui/placements/{task['id']}/top_down_houses", json={"width": -1})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/api/ui/placements?mode=unknown").status_code, 422)

    def test_sql_server_index_columns_have_bounded_lengths_and_unicode_tag(self):
        from sqlalchemy import String, UniqueConstraint
        from sqlalchemy.dialects import mssql
        from sqlalchemy.schema import CreateTable, CreateIndex
        from app.database import Base
        dialect = mssql.dialect(deprecate_large_types=True)
        self.assertEqual(str(models.Task.__table__.c.tag.type.compile(dialect=dialect)), "NVARCHAR(100)")
        for table in Base.metadata.tables.values():
            self.assertIn("CREATE TABLE", str(CreateTable(table).compile(dialect=dialect)))
            keyed_columns = []
            for index in table.indexes:
                str(CreateIndex(index).compile(dialect=dialect))
                keyed_columns.extend(index.columns)
            for constraint in table.constraints:
                if isinstance(constraint, UniqueConstraint):
                    keyed_columns.extend(constraint.columns)
            for column in keyed_columns:
                if isinstance(column.type, String):
                    with self.subTest(table=table.name, column=column.name):
                        self.assertIsNotNone(column.type.length, "SQL Server cannot index NVARCHAR(MAX)")

    def test_shop_repeat_purchase_does_not_charge_twice(self):
        from app.seed import seed_if_empty
        with SessionLocal() as session:
            seed_if_empty(session)
            # Controlled balance fixture; reward earning is covered separately.
            session.scalars(select(models.Team).order_by(models.Team.id)).first().coins = 500
            session.commit()
        team = self.request("GET", "/api/teams")[0]
        item = next(row for row in self.request("GET", "/api/shop-items") if 0 < row["cost"] <= team["coins"])
        purchased = self.request("POST", f"/api/teams/{team['id']}/shop-items/{item['id']}/purchase")
        self.assertTrue(purchased["owned"])
        after = self.request("GET", f"/api/teams/{team['id']}")
        self.assertEqual(after["coins"], team["coins"] - item["cost"])
        repeated = self.client.post(f"/api/teams/{team['id']}/shop-items/{item['id']}/purchase")
        self.assertIn(repeated.status_code, (200, 400, 409))
        self.assertEqual(self.request("GET", f"/api/teams/{team['id']}")["coins"], after["coins"])

    def test_quest_rewards_require_confirmation_and_cannot_repeat(self):
        task, team = self.selected_task()
        task_id, team_id = task["id"], team["id"]
        steps = self.request("GET", f"/api/tasks/{task_id}/quests")
        self.assertGreaterEqual(len(steps), 2)
        step = next(row for row in steps if row["status"] == "current")
        before = self.request("GET", f"/api/teams/{team_id}")
        self.submit(task_id, step["id"])
        self.assertEqual(self.request("GET", f"/api/teams/{team_id}")["experience"], before["experience"])
        self.request("POST", f"/api/tasks/{task_id}/quests/{step['id']}/confirm")
        confirmed = self.request("GET", f"/api/teams/{team_id}")
        self.assertGreater(confirmed["experience"], before["experience"])
        self.assertGreater(confirmed["coins"], before["coins"])
        repeated = self.client.post(f"/api/tasks/{task_id}/quests/{step['id']}/confirm")
        self.assertIn(repeated.status_code, (200, 400, 409))
        again = self.request("GET", f"/api/teams/{team_id}")
        self.assertEqual(again["experience"], confirmed["experience"])
        self.assertEqual(again["coins"], confirmed["coins"])

    def test_progress_rewards_each_selected_team_only_and_preserves_task_rating(self):
        task = self.task(publish=True)
        teams = [self.team(name) for name in ("Альфа", "Бета", "Гамма")]
        for index, team in enumerate(teams):
            response = self.propose(task["id"], team["id"])
            if index < 2:
                self.request("PATCH", f"/api/responses/{response['id']}/select")
        step = self.request("GET", f"/api/tasks/{task['id']}/quests")[0]
        premature = self.client.post(f"/api/tasks/{task['id']}/quests/{step['id']}/confirm")
        self.assertIn(premature.status_code, (400, 409))
        empty = self.client.post(f"/api/tasks/{task['id']}/quests/{step['id']}/submit", json={"submission_text": " "})
        self.assertEqual(empty.status_code, 422)
        self.request("POST", f"/api/tasks/{task['id']}/quests/{step['id']}/hint")
        self.submit(task["id"], step["id"])
        self.request("POST", f"/api/tasks/{task['id']}/quests/{step['id']}/confirm")
        updated = [self.request("GET", f"/api/teams/{team['id']}") for team in teams]
        self.assertGreater(updated[0]["experience"], 0)
        self.assertEqual(updated[0]["experience"], updated[1]["experience"])
        self.assertEqual(updated[0]["coins"], updated[1]["coins"])
        self.assertEqual(updated[2]["experience"], 0)
        self.assertEqual(updated[2]["coins"], 0)
        self.assertEqual(self.request("GET", f"/api/tasks/{task['id']}")["score"], 100)

    def test_boss_reopening_does_not_repeat_rewards(self):
        task, team = self.selected_task()
        task_id, team_id = task["id"], team["id"]
        for step in self.request("GET", f"/api/tasks/{task_id}/quests"):
            self.submit(task_id, step["id"])
            self.request("POST", f"/api/tasks/{task_id}/quests/{step['id']}/confirm")
        status = self.request("GET", f"/api/tasks/{task_id}/boss-criteria")
        self.assertGreater(status["total"], 0)
        for criterion in status["criteria"]:
            if not criterion["confirmed"]:
                status = self.request("PATCH", f"/api/tasks/{task_id}/boss-criteria/{criterion['id']}/toggle")
        self.assertTrue(status["completed"])
        rewarded = self.request("GET", f"/api/teams/{team_id}")
        last_id = status["criteria"][-1]["id"]
        self.request("PATCH", f"/api/tasks/{task_id}/boss-criteria/{last_id}/toggle")
        self.request("PATCH", f"/api/tasks/{task_id}/boss-criteria/{last_id}/toggle")
        again = self.request("GET", f"/api/teams/{team_id}")
        self.assertEqual(again["experience"], rewarded["experience"])
        self.assertEqual(again["coins"], rewarded["coins"])

    def test_seed_and_application_restart_do_not_duplicate_data(self):
        from app.seed import seed_if_empty
        counted_models = (models.Task, models.Team, models.ShopItem, models.QuestStep, models.TeamResponse)
        with SessionLocal() as session:
            seed_if_empty(session)
            counts = {m.__tablename__: session.scalar(select(func.count()).select_from(m)) for m in counted_models}
            seed_if_empty(session)
            repeated = {m.__tablename__: session.scalar(select(func.count()).select_from(m)) for m in counted_models}
        self.assertEqual(counts, repeated)
        self.assertGreaterEqual(counts["tasks"], 10)
        self.assertGreaterEqual(counts["teams"], 5)
        self.assertGreaterEqual(counts["team_responses"], 5)
        self.assertGreaterEqual(len(self.request("GET", "/api/tasks?status=published")), 5)
        self.assertGreaterEqual(len(self.request("GET", "/api/tasks?status=draft")), 5)
        self.client.__exit__(None, None, None)
        engine.dispose()
        self.client = TestClient(app)
        self.client.__enter__()
        with SessionLocal() as session:
            restarted = {m.__tablename__: session.scalar(select(func.count()).select_from(m)) for m in counted_models}
        self.assertEqual(counts, restarted)

    def test_unknown_resources_return_404(self):
        for path in ("/api/tasks/999999", "/api/teams/999999", "/api/tasks/999999/questions"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


def tearDownModule():
    engine.dispose()
    _temp.cleanup()


if __name__ == "__main__":
    unittest.main()
