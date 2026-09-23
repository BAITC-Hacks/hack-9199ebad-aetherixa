"""Additive migration regression checks against an isolated legacy SQLite fixture."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from sqlalchemy import Column, Index, MetaData, Table, create_engine, inspect, text
from sqlalchemy.dialects import mssql

from app.migrations import _upgrade_tag_unicode, migrate_existing_schema


class LegacyMigrationTests(unittest.TestCase):
    def test_migration_preserves_rows_and_repeated_runs_preserve_new_confirmation(self):
        with tempfile.TemporaryDirectory(prefix="ai_sana_legacy_") as directory:
            engine = create_engine("sqlite:///" + (Path(directory) / "legacy.sqlite3").as_posix())
            try:
                with engine.begin() as connection:
                    connection.execute(text("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, tag TEXT, data_sources TEXT DEFAULT '', score INTEGER, level TEXT)"))
                    connection.execute(text("INSERT INTO tasks (id,title,tag,score,level) VALUES (1, :title, :tag, 85, 'ready')"),
                                       {"title": "Задача до обновления", "tag": "поддержка"})
                    connection.execute(text("CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT)"))
                    connection.execute(text("INSERT INTO teams VALUES (1, 'Существующая команда')"))
                    connection.execute(text("CREATE TABLE team_responses (id INTEGER PRIMARY KEY)"))
                    connection.execute(text("CREATE TABLE quest_steps (id INTEGER PRIMARY KEY)"))
                migrate_existing_schema(engine)
                inspector = inspect(engine)
                expected_columns = {
                    "tasks": {"draft_text", "status", "confirmed_at", "published_at"},
                    "teams": {"interests", "skills", "technologies"},
                    "team_responses": {"deadline_days"},
                    "quest_steps": {"submission_text"},
                }
                for table, expected in expected_columns.items():
                    with self.subTest(table=table):
                        self.assertTrue(expected.issubset({column["name"] for column in inspector.get_columns(table)}))
                with engine.begin() as connection:
                    row = connection.execute(text("SELECT * FROM tasks WHERE id = 1")).mappings().one()
                    self.assertEqual(row["title"], "Задача до обновления")
                    self.assertEqual(row["score"], 0)
                    self.assertEqual(row["status"], "draft")
                    self.assertIsNone(row["confirmed_at"])
                    connection.execute(text("UPDATE tasks SET status='published', confirmed_at='2026-09-23 10:00:00', score=100, level='priority' WHERE id=1"))
                migrate_existing_schema(engine)
                migrate_existing_schema(engine)
                with engine.connect() as connection:
                    row = connection.execute(text("SELECT * FROM tasks WHERE id = 1")).mappings().one()
                    self.assertEqual(row["score"], 100)
                    self.assertEqual(row["status"], "published")
                    self.assertIsNotNone(row["confirmed_at"])
                    self.assertEqual(connection.scalar(text("SELECT COUNT(*) FROM tasks")), 1)
                    self.assertEqual(connection.scalar(text("SELECT name FROM teams WHERE id=1")), "Существующая команда")
            finally:
                engine.dispose()

    def test_incompatible_original_schema_is_refused_without_changing_rows(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE tasks (id INTEGER PRIMARY KEY, raw_description TEXT, readiness_score INTEGER)"))
                connection.execute(text("INSERT INTO tasks VALUES (1, 'Исходная задача', 75)"))
            with self.assertRaises(RuntimeError):
                migrate_existing_schema(engine)
            self.assertEqual({column["name"] for column in inspect(engine).get_columns("tasks")},
                             {"id", "raw_description", "readiness_score"})
            with engine.connect() as connection:
                self.assertEqual(connection.scalar(text("SELECT readiness_score FROM tasks WHERE id=1")), 75)
        finally:
            engine.dispose()


class SQLServerMigrationPlanningTests(unittest.TestCase):
    """Validate generated migration operations, without claiming a live SQL Server check."""

    @staticmethod
    def ordinary_index(**changes):
        metadata = dict(name="ix_tasks_tag", type=2, is_unique=0, is_primary_key=0,
                        is_unique_constraint=0, has_filter=0, is_disabled=0,
                        is_hypothetical=0, fill_factor=0, is_padded=0, ignore_dup_key=0,
                        allow_row_locks=1, allow_page_locks=1, space_type="FG",
                        default_filegroup=1, column_count=1, special_columns=0,
                        compressed_partitions=0)
        return {**metadata, **changes}

    def test_already_unicode_tag_is_noop_and_unexpected_length_is_refused(self):
        connection, inspector = Mock(), Mock(default_schema_name="dbo")
        _upgrade_tag_unicode(connection, inspector, [{"name": "tag", "type": mssql.NVARCHAR(100), "nullable": False}])
        connection.execute.assert_not_called()
        with self.assertRaises(RuntimeError):
            _upgrade_tag_unicode(connection, inspector, [{"name": "tag", "type": mssql.VARCHAR(200), "nullable": False}])
        connection.execute.assert_not_called()

    def test_custom_index_is_refused_before_any_schema_change(self):
        for change in ({"is_unique": 1}, {"special_columns": 1}, {"has_filter": 1},
                       {"compressed_partitions": 1}, {"name": "custom_index"}):
            with self.subTest(change=change):
                connection = Mock()
                connection.execute.return_value.mappings.return_value.all.return_value = [self.ordinary_index(**change)]
                with self.assertRaises(RuntimeError):
                    _upgrade_tag_unicode(connection, Mock(default_schema_name="dbo"),
                                         [{"name": "tag", "type": mssql.VARCHAR(100), "nullable": False}])
                self.assertEqual(connection.execute.call_count, 1)
                self.assertNotIn("ALTER TABLE", str(connection.execute.call_args.args[0]))

    def test_dependent_objects_refuse_conversion_before_ddl(self):
        connection = Mock()
        index_result = Mock()
        index_result.mappings.return_value.all.return_value = [self.ordinary_index()]
        dependency_result = Mock()
        dependency_result.scalar_one.return_value = 1
        connection.execute.side_effect = [index_result, dependency_result]
        with self.assertRaises(RuntimeError):
            _upgrade_tag_unicode(connection, Mock(default_schema_name="dbo"),
                                 [{"name": "tag", "type": mssql.VARCHAR(100), "nullable": False}])
        self.assertEqual(connection.execute.call_count, 2)
        self.assertTrue(all("ALTER TABLE" not in str(call.args[0]) for call in connection.execute.call_args_list))

    def test_known_index_is_restored_and_collation_nullability_preserved(self):
        for nullable in (False, True):
            with self.subTest(nullable=nullable):
                connection = Mock()
                connection.dialect = mssql.dialect()
                operations = []
                index_result, dependency_result, collation_result = Mock(), Mock(), Mock()
                index_result.mappings.return_value.all.return_value = [self.ordinary_index()]
                dependency_result.scalar_one.return_value = 0
                collation_result.scalar_one.return_value = "Cyrillic_General_CI_AS"
                results = iter([index_result, dependency_result, collation_result])

                def execute(statement, *args):
                    sql = str(statement)
                    if sql.startswith("ALTER TABLE"):
                        operations.append(sql)
                        return Mock()
                    return next(results)

                connection.execute.side_effect = execute
                reflected = Table("tasks", MetaData(), Column("tag", mssql.VARCHAR(100), nullable=nullable), schema="dbo")
                index = Index("ix_tasks_tag", reflected.c.tag)
                with patch("app.migrations.Table", return_value=reflected), \
                     patch.object(index, "drop", side_effect=lambda conn: operations.append("DROP INDEX")), \
                     patch.object(index, "create", side_effect=lambda conn: operations.append("CREATE INDEX")):
                    _upgrade_tag_unicode(connection, Mock(default_schema_name="dbo"),
                                         [{"name": "tag", "type": mssql.VARCHAR(100), "nullable": nullable}])
                self.assertEqual(operations[0], "DROP INDEX")
                self.assertEqual(operations[-1], "CREATE INDEX")
                self.assertEqual(len(operations), 3)
                self.assertIn("NVARCHAR(100)", operations[1])
                expected_suffix = "COLLATE [Cyrillic_General_CI_AS] " + ("NULL" if nullable else "NOT NULL")
                self.assertTrue(operations[1].endswith(expected_suffix))


if __name__ == "__main__":
    unittest.main()
