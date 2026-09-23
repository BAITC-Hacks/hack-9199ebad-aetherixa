"""Additive MVP migration: keeps existing rows, requires confirming old cards."""
from sqlalchemy import MetaData, Table, inspect, text
from sqlalchemy.exc import SQLAlchemyError


def _upgrade_tag_unicode(conn, inspector, columns):
    """Convert the known legacy VARCHAR(100) tag without losing its index.

    Only the original ordinary ix_tasks_tag is supported. Custom dependent
    objects/options require a reviewed migration and are rejected transactionally.
    SQL Server rolls back the index drop if conversion/recreation fails.
    """
    column = next(item for item in columns if item["name"] == "tag")
    kind = str(column["type"]).upper()
    if not kind.startswith("VARCHAR"):
        return
    if getattr(column["type"], "length", None) != 100:
        raise RuntimeError("Миграция tasks.tag ожидает VARCHAR(100). Нестандартный тип требует отдельной миграции; изменения отменены.")
    schema = inspector.default_schema_name or "dbo"
    object_name = f"{schema}.tasks"
    params = {"object_name": object_name}
    index_rows = conn.execute(text("""
        SELECT i.name, i.type, i.is_unique, i.is_primary_key, i.is_unique_constraint,
               i.has_filter, i.is_disabled, i.is_hypothetical, i.fill_factor,
               i.is_padded, i.ignore_dup_key, i.allow_row_locks, i.allow_page_locks,
               ds.type AS space_type, fg.is_default AS default_filegroup,
               (SELECT COUNT(*) FROM sys.index_columns x WHERE x.object_id=i.object_id AND x.index_id=i.index_id) AS column_count,
               (SELECT COUNT(*) FROM sys.index_columns x WHERE x.object_id=i.object_id AND x.index_id=i.index_id
                    AND (x.is_descending_key=1 OR x.is_included_column=1)) AS special_columns,
               (SELECT COUNT(*) FROM sys.partitions p WHERE p.object_id=i.object_id AND p.index_id=i.index_id
                    AND p.data_compression<>0) AS compressed_partitions
        FROM sys.indexes i
        JOIN sys.data_spaces ds ON ds.data_space_id=i.data_space_id
        LEFT JOIN sys.filegroups fg ON fg.data_space_id=i.data_space_id
        WHERE i.object_id=OBJECT_ID(:object_name)
          AND EXISTS (SELECT 1 FROM sys.index_columns ic JOIN sys.columns c
                      ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                      WHERE ic.object_id=i.object_id AND ic.index_id=i.index_id AND c.name='tag')
    """), params).mappings().all()
    for index in index_rows:
        ordinary = (index["name"] == "ix_tasks_tag" and index["type"] == 2
                    and not any(index[key] for key in ("is_unique", "is_primary_key", "is_unique_constraint",
                            "has_filter", "is_disabled", "is_hypothetical", "fill_factor", "is_padded",
                            "ignore_dup_key", "special_columns", "compressed_partitions"))
                    and index["allow_row_locks"] and index["allow_page_locks"]
                    and index["column_count"] == 1 and index["space_type"] == "FG" and index["default_filegroup"])
        if not ordinary:
            raise RuntimeError(f"tasks.tag зависит от нестандартного индекса {index['name']}. Нужна отдельная миграция; изменения отменены.")
    dependencies = conn.execute(text("""
        SELECT
          (SELECT COUNT(*) FROM sys.sql_expression_dependencies d
           WHERE d.referenced_id=OBJECT_ID(:object_name)
             AND d.referenced_minor_id IN (0, COLUMNPROPERTY(OBJECT_ID(:object_name), 'tag', 'ColumnId')))
          + (SELECT COUNT(*) FROM sys.foreign_key_columns f
             WHERE (f.parent_object_id=OBJECT_ID(:object_name) AND f.parent_column_id=COLUMNPROPERTY(OBJECT_ID(:object_name), 'tag', 'ColumnId'))
                OR (f.referenced_object_id=OBJECT_ID(:object_name) AND f.referenced_column_id=COLUMNPROPERTY(OBJECT_ID(:object_name), 'tag', 'ColumnId')))
          + (SELECT COUNT(*) FROM sys.stats s JOIN sys.stats_columns sc ON sc.object_id=s.object_id AND sc.stats_id=s.stats_id
             WHERE s.object_id=OBJECT_ID(:object_name) AND s.user_created=1
               AND sc.column_id=COLUMNPROPERTY(OBJECT_ID(:object_name), 'tag', 'ColumnId'))
          + (SELECT COUNT(*) FROM sys.fulltext_index_columns f WHERE f.object_id=OBJECT_ID(:object_name)
               AND f.column_id=COLUMNPROPERTY(OBJECT_ID(:object_name), 'tag', 'ColumnId'))
          + (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id=OBJECT_ID(:object_name) AND c.name='tag'
               AND (c.default_object_id<>0 OR c.rule_object_id<>0))
    """), params).scalar_one()
    if dependencies:
        raise RuntimeError("tasks.tag имеет дополнительные зависимости (ограничения, представления или статистика). Нужна отдельная миграция; изменения отменены.")
    reflected = Table("tasks", MetaData(), schema=schema, autoload_with=conn, resolve_fks=False)
    indexes = [index for index in reflected.indexes if index.name in {row["name"] for row in index_rows}]
    if len(indexes) != len(index_rows):
        raise RuntimeError("Не удалось прочитать определение индекса tasks.tag; изменения отменены.")
    preparer = conn.dialect.identifier_preparer
    table_name = f"{preparer.quote_schema(schema)}.{preparer.quote('tasks')}"
    collation = conn.execute(text("SELECT collation_name FROM sys.columns WHERE object_id=OBJECT_ID(:object_name) AND name='tag'"), params).scalar_one()
    nullability = "NULL" if column["nullable"] else "NOT NULL"
    collation_sql = f" COLLATE {preparer.quote(collation)}" if collation else ""
    try:
        for index in indexes:
            index.drop(conn)
        conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN [tag] NVARCHAR(100){collation_sql} {nullability}"))
        for index in indexes:
            index.create(conn)
    except SQLAlchemyError as exc:
        raise RuntimeError("Не удалось обновить tasks.tag и восстановить индекс. Транзакция отменена; исходные данные и индекс сохранены.") from exc


def migrate_existing_schema(engine):
    # Read schema through the same transaction/connection used for alterations.
    # On SQL Server a second connection would wait for our own schema lock.
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        metadata = {table: inspector.get_columns(table) for table in tables}
        if "tasks" in tables:
            fields = {column["name"] for column in metadata["tasks"]}
            if not {"tag", "data_sources", "score", "level"}.issubset(fields):
                raise RuntimeError("Несовместимая схема tasks. Выберите aetherix_backend; aetherix_db от database_schema.py не изменена.")
        mssql = engine.dialect.name == "mssql"
        if mssql and "tasks" in tables:
            _upgrade_tag_unicode(conn, inspector, metadata["tasks"])
        text_type = "NVARCHAR(MAX)" if mssql else "TEXT"
        additions = {
            "tasks": {"draft_text": f"{text_type} NOT NULL DEFAULT ''",
                      "status": "NVARCHAR(20) NOT NULL DEFAULT 'draft'" if mssql else "TEXT NOT NULL DEFAULT 'draft'",
                      "confirmed_at": "DATETIME NULL", "published_at": "DATETIME NULL"},
            "teams": {name: f"{text_type} NOT NULL DEFAULT ''" for name in ("interests", "skills", "technologies")},
            "team_responses": {"deadline_days": "INT NULL"},
            "quest_steps": {"submission_text": f"{text_type} NOT NULL DEFAULT ''"},
        }
        for table, fields in additions.items():
            if table not in tables:
                continue
            columns = {c["name"] for c in metadata[table]}
            for field, definition in fields.items():
                if field not in columns:
                    conn.execute(text(f"ALTER TABLE [{table}] ADD [{field}] {definition}"))
            if table == "tasks" and "confirmed_at" not in columns:
                conn.execute(text("UPDATE [tasks] SET [score] = 0, [level] = 'draft'"))
        if not mssql:
            return
        user_text_columns = {
            "tasks": {"title", "context_need", "data_sources", "expected_result", "success_criteria",
                      "constraints", "users", "contact_format", "selected_team_name"},
            "teams": {"name", "avatar_emoji"},
            "team_responses": {"team_name", "idea", "plan", "prototype_link"},
            "team_members": {"name", "title"},
            "quest_steps": {"title", "path_choice"},
            "boss_criteria": {"text"},
            "shop_items": {"name", "icon"},
            "ui_placement_modes": {"name", "description"},
            "task_ui_placements": {"visual_config_json"},
        }
        for table in tables.intersection(user_text_columns):
            indexed = {name for index in inspector.get_indexes(table) for name in index["column_names"]}
            indexed.update(name for unique in inspector.get_unique_constraints(table) for name in unique["column_names"])
            for column in metadata[table]:
                kind = str(column["type"]).upper()
                name = column["name"]
                if name not in user_text_columns[table] or name in indexed or not (kind.startswith("VARCHAR") or kind == "TEXT"):
                    continue
                nullable = "NULL" if column["nullable"] else "NOT NULL"
                conn.execute(text(f"ALTER TABLE [{table}] ALTER COLUMN [{name}] NVARCHAR(MAX) {nullable}"))
