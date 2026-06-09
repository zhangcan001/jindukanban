from collections.abc import Generator
import ast
import logging
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


import os as _os

_SQLITE_WAL_DISABLED = _os.environ.get("DISABLE_SQLITE_WAL", "").lower() in ("1", "true", "yes")


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            if not _SQLITE_WAL_DISABLED:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"
_ALEMBIC_VERSIONS_DIR = _BACKEND_DIR / "alembic" / "versions"


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _stamp_existing_pre_alembic_db() -> bool:
    """If DB has app tables but no alembic_version, stamp it as baseline.

    Returns True if a stamp was performed.
    """
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "alembic_version" in table_names:
        return False
    if "project" not in table_names:
        return False
    from alembic import command

    logger.info("detected pre-alembic database; stamping at baseline")
    command.stamp(_alembic_config(), "head")
    return True


def _migration_heads_from_files() -> set[str]:
    revisions: set[str] = set()
    down_revisions: set[str] = set()
    for path in _ALEMBIC_VERSIONS_DIR.glob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            return set()
        revision = None
        down_revision = None
        for node in tree.body:
            target_nodes: list[ast.expr] = []
            value_node = None
            if isinstance(node, ast.Assign):
                target_nodes = list(node.targets)
                value_node = node.value
            elif isinstance(node, ast.AnnAssign):
                target_nodes = [node.target]
                value_node = node.value
            for target in target_nodes:
                if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"} and value_node is not None:
                    try:
                        value = ast.literal_eval(value_node)
                    except (TypeError, ValueError):
                        value = None
                    if target.id == "revision" and isinstance(value, str):
                        revision = value
                    elif target.id == "down_revision":
                        down_revision = value
        if revision:
            revisions.add(revision)
        if isinstance(down_revision, str):
            down_revisions.add(down_revision)
        elif isinstance(down_revision, (list, tuple)):
            down_revisions.update(value for value in down_revision if isinstance(value, str))
    return revisions - down_revisions


def _database_at_migration_head() -> bool:
    heads = _migration_heads_from_files()
    if not heads:
        return False
    try:
        with engine.connect() as connection:
            table_exists = connection.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'")
            ).first()
            if table_exists is None:
                return False
            rows = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    except Exception:
        return False
    current = {str(row[0]) for row in rows if row[0]}
    return current == heads


def run_migrations() -> None:
    if _database_at_migration_head():
        return
    import app.models  # noqa: F401  ensure metadata is loaded

    _stamp_existing_pre_alembic_db()
    from alembic import command

    command.upgrade(_alembic_config(), "head")


def init_db() -> None:
    import app.models  # noqa: F401

    run_migrations()
    _ensure_lightweight_columns()


def _ensure_lightweight_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "report_export_record" in tables:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(report_export_record)"))}
            if "data_date" not in columns:
                connection.execute(text("ALTER TABLE report_export_record ADD COLUMN data_date DATE"))

        if "project" in tables:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(project)"))}
            if "template_id" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN template_id INTEGER"))
            if "dashboard_config" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN dashboard_config TEXT"))
            if "report_config" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN report_config TEXT"))
            if "ai_config" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN ai_config TEXT"))
            if "default_calculation_profile_id" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN default_calculation_profile_id INTEGER"))
            if "default_calculation_method" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN default_calculation_method VARCHAR(100) DEFAULT 'auto'"))
            if "default_baseline_plan_id" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN default_baseline_plan_id INTEGER"))
            if "is_archived" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN is_archived BOOLEAN DEFAULT 0"))
            if "archived_at" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN archived_at DATETIME"))
            if "archive_remark" not in columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN archive_remark TEXT"))

        if "baseline_plan" in tables:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(baseline_plan)"))}
            if "baseline_date" not in columns:
                connection.execute(text("ALTER TABLE baseline_plan ADD COLUMN baseline_date DATE"))

        if "baseline_plan_snapshot" not in tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE baseline_plan_snapshot (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        baseline_plan_id INTEGER NOT NULL,
                        snapshot_date DATE,
                        label VARCHAR(255) NOT NULL,
                        description TEXT,
                        payload TEXT NOT NULL,
                        item_count INTEGER NOT NULL DEFAULT 0,
                        created_by VARCHAR(100),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES project (id),
                        FOREIGN KEY(baseline_plan_id) REFERENCES baseline_plan (id)
                    )
                    """
                )
            )
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_baseline_plan_snapshot_baseline ON baseline_plan_snapshot (baseline_plan_id)")
            )
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_baseline_plan_snapshot_project ON baseline_plan_snapshot (project_id)")
            )

        if "import_batch" in tables:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(import_batch)"))}
            if "calculation_profile_id" not in columns:
                connection.execute(text("ALTER TABLE import_batch ADD COLUMN calculation_profile_id INTEGER"))
            if "baseline_plan_id" not in columns:
                connection.execute(text("ALTER TABLE import_batch ADD COLUMN baseline_plan_id INTEGER"))
            if "import_group_id" not in columns:
                connection.execute(text("ALTER TABLE import_batch ADD COLUMN import_group_id VARCHAR(100)"))
            if "import_group_name" not in columns:
                connection.execute(text("ALTER TABLE import_batch ADD COLUMN import_group_name VARCHAR(255)"))
            if "is_frozen" not in columns:
                connection.execute(text("ALTER TABLE import_batch ADD COLUMN is_frozen BOOLEAN DEFAULT 0"))
            if "frozen_at" not in columns:
                connection.execute(text("ALTER TABLE import_batch ADD COLUMN frozen_at DATETIME"))
            if "freeze_remark" not in columns:
                connection.execute(text("ALTER TABLE import_batch ADD COLUMN freeze_remark TEXT"))

        if "progress_item" in tables:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(progress_item)"))}
            if "construction_unit" not in columns:
                connection.execute(text("ALTER TABLE progress_item ADD COLUMN construction_unit VARCHAR(255)"))
            if "imported_planned_percent" not in columns:
                connection.execute(text("ALTER TABLE progress_item ADD COLUMN imported_planned_percent FLOAT"))
                if "planned_percent" in columns:
                    connection.execute(text("UPDATE progress_item SET imported_planned_percent = planned_percent WHERE imported_planned_percent IS NULL"))
            if "schedule_phase" not in columns:
                connection.execute(text("ALTER TABLE progress_item ADD COLUMN schedule_phase VARCHAR(50)"))
            # 同批次内 identity_key 唯一——避免重复行扭曲后续统计（identity_key 为空的兜底行不约束）
            indexes = {row[1] for row in connection.execute(text("PRAGMA index_list(progress_item)"))}
            if "uq_progress_item_batch_identity" not in indexes:
                # 先清理潜在重复，避免新建唯一索引时报错
                connection.execute(
                    text(
                        """
                        DELETE FROM progress_item
                        WHERE id IN (
                            SELECT pi.id FROM progress_item pi
                            JOIN (
                                SELECT batch_id, identity_key, MIN(id) AS keep_id
                                FROM progress_item
                                WHERE identity_key IS NOT NULL AND identity_key != ''
                                GROUP BY batch_id, identity_key
                                HAVING COUNT(*) > 1
                            ) dup
                              ON pi.batch_id = dup.batch_id
                             AND pi.identity_key = dup.identity_key
                             AND pi.id != dup.keep_id
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_progress_item_batch_identity "
                        "ON progress_item (batch_id, identity_key) "
                        "WHERE identity_key IS NOT NULL AND identity_key != ''"
                    )
                )
            # 热路径非唯一索引——dashboard/analytics 走 (project_id, batch_id),
            # _find_previous_item 按 task_id 跨批次找上期数据,status 是常用筛选。
            if "ix_progress_item_project_batch" not in indexes:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_progress_item_project_batch "
                        "ON progress_item (project_id, batch_id)"
                    )
                )
            if "ix_progress_item_task_id" not in indexes:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_progress_item_task_id "
                        "ON progress_item (task_id)"
                    )
                )
            if "ix_progress_item_batch_status" not in indexes:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_progress_item_batch_status "
                        "ON progress_item (batch_id, status)"
                    )
                )

        if "progress_item_edit_history" in tables:
            # edit_session_id 用于把"同一次 PUT 产生的多行历史"归到一起,撤销时直接
            # WHERE edit_session_id = ?,比"reason + 2 秒窗口"那套近似算法可靠。
            history_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(progress_item_edit_history)"))}
            if "edit_session_id" not in history_columns:
                connection.execute(text("ALTER TABLE progress_item_edit_history ADD COLUMN edit_session_id VARCHAR(36)"))
            history_indexes = {row[1] for row in connection.execute(text("PRAGMA index_list(progress_item_edit_history)"))}
            if "ix_progress_item_edit_history_session" not in history_indexes:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_progress_item_edit_history_session "
                        "ON progress_item_edit_history (progress_item_id, edit_session_id)"
                    )
                )

        if "maintenance_log" not in tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE maintenance_log (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        action VARCHAR(100) NOT NULL,
                        target_type VARCHAR(100),
                        target_id INTEGER,
                        summary VARCHAR(255) NOT NULL,
                        detail TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
                    )
                    """
                )
            )

        if "mapping_template" in tables:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(mapping_template)"))}
            if "project_type" not in columns:
                connection.execute(text("ALTER TABLE mapping_template ADD COLUMN project_type VARCHAR(100)"))
            if "sheet_name" not in columns:
                connection.execute(text("ALTER TABLE mapping_template ADD COLUMN sheet_name VARCHAR(255)"))
            if "field_structure" not in columns:
                connection.execute(text("ALTER TABLE mapping_template ADD COLUMN field_structure TEXT"))
            if "is_active" not in columns:
                connection.execute(text("ALTER TABLE mapping_template ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            if "last_used_at" not in columns:
                connection.execute(text("ALTER TABLE mapping_template ADD COLUMN last_used_at DATETIME"))
            if "use_count" not in columns:
                connection.execute(text("ALTER TABLE mapping_template ADD COLUMN use_count INTEGER DEFAULT 0"))
            if "header_hash" not in columns:
                connection.execute(text("ALTER TABLE mapping_template ADD COLUMN header_hash VARCHAR(64)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mapping_template_header_hash ON mapping_template (header_hash)"))

        if "rectification_item" in tables:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(rectification_item)"))}
            expected_columns = {
                "source_type": "VARCHAR(50)",
                "source_id": "INTEGER",
                "responsible_unit": "VARCHAR(255)",
                "review_result": "TEXT",
                "closed_at": "DATETIME",
            }
            for column_name, column_type in expected_columns.items():
                if column_name not in columns:
                    connection.execute(text(f"ALTER TABLE rectification_item ADD COLUMN {column_name} {column_type}"))

        if "rectification_action_log" not in tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE rectification_action_log (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        rectification_item_id INTEGER NOT NULL,
                        project_id INTEGER NOT NULL,
                        action VARCHAR(50) NOT NULL,
                        from_status VARCHAR(50),
                        to_status VARCHAR(50),
                        content TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        FOREIGN KEY(rectification_item_id) REFERENCES rectification_item (id),
                        FOREIGN KEY(project_id) REFERENCES project (id)
                    )
                    """
                )
            )

        if "ai_prompt_template" not in tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE ai_prompt_template (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER,
                        name VARCHAR(100) NOT NULL,
                        code VARCHAR(100) NOT NULL,
                        description TEXT,
                        prompt_template TEXT NOT NULL,
                        is_builtin BOOLEAN DEFAULT 0,
                        is_active BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
                    )
                    """
                )
            )

        if "calculation_profile" in tables:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(calculation_profile)"))}
            if "delay_threshold_ahead" not in columns:
                connection.execute(text("ALTER TABLE calculation_profile ADD COLUMN delay_threshold_ahead FLOAT NOT NULL DEFAULT 5"))
            if "delay_threshold_normal" not in columns:
                connection.execute(text("ALTER TABLE calculation_profile ADD COLUMN delay_threshold_normal FLOAT NOT NULL DEFAULT -5"))
            if "delay_threshold_minor" not in columns:
                connection.execute(text("ALTER TABLE calculation_profile ADD COLUMN delay_threshold_minor FLOAT NOT NULL DEFAULT -10"))
            if "delay_threshold_major" not in columns:
                connection.execute(text("ALTER TABLE calculation_profile ADD COLUMN delay_threshold_major FLOAT NOT NULL DEFAULT -20"))
            if "delay_threshold_overrides" not in columns:
                connection.execute(text("ALTER TABLE calculation_profile ADD COLUMN delay_threshold_overrides TEXT"))

        if "column_alias_history" not in tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE column_alias_history (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER,
                        raw_header VARCHAR(512) NOT NULL,
                        normalized_header VARCHAR(512) NOT NULL,
                        system_field VARCHAR(100) NOT NULL,
                        field_type VARCHAR(50),
                        hit_count INTEGER NOT NULL DEFAULT 1,
                        last_used_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES project (id),
                        CONSTRAINT uq_column_alias_scope_header_field UNIQUE (project_id, normalized_header, system_field)
                    )
                    """
                )
            )
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_column_alias_normalized_header ON column_alias_history (normalized_header)")
            )

        if "ai_call_log" not in tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE ai_call_log (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER,
                        batch_id INTEGER,
                        mode VARCHAR(100) NOT NULL,
                        model VARCHAR(100),
                        source VARCHAR(50) NOT NULL,
                        success BOOLEAN DEFAULT 0,
                        error_message TEXT,
                        prompt_tokens INTEGER,
                        completion_tokens INTEGER,
                        input_summary_length INTEGER,
                        output_length INTEGER,
                        duration_ms INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
                    )
                    """
                )
            )
        elif "ai_call_log" in tables:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(ai_call_log)"))}
            if "input_summary_length" not in columns:
                connection.execute(text("ALTER TABLE ai_call_log ADD COLUMN input_summary_length INTEGER"))
            if "output_length" not in columns:
                connection.execute(text("ALTER TABLE ai_call_log ADD COLUMN output_length INTEGER"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
