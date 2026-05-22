from app.database import SessionLocal
from app.models.import_batch import ImportBatch
from app.models.project import Project
from app.services.import_confirm_service import _match_or_create_task


def test_same_wbs_and_name_matches_existing_progress_task() -> None:
    db = SessionLocal()
    try:
        project = Project(name="WBS任务匹配测试")
        db.add(project)
        db.flush()
        row = {"wbs_code": "JD.01", "task_name": "桥架安装", "building": "1号楼", "floor": "1层", "discipline": "电气"}

        first_task, first_created = _match_or_create_task(db, project.id, row, 1)
        second_task, second_created = _match_or_create_task(db, project.id, row, 2)

        assert first_created is True
        assert second_created is False
        assert second_task.id == first_task.id
    finally:
        db.close()


def test_same_identity_key_matches_existing_progress_task() -> None:
    db = SessionLocal()
    try:
        project = Project(name="identity任务匹配测试")
        batch = ImportBatch(project_id=1, file_name="unused.csv")
        db.add_all([project, batch])
        db.flush()
        first_row = {"identity_key": "task-001", "task_name": "桥架安装", "building": "1号楼"}
        second_row = {"identity_key": "task-001", "task_name": "桥架安装二期", "building": "2号楼"}

        first_task, first_created = _match_or_create_task(db, project.id, first_row, 1)
        second_task, second_created = _match_or_create_task(db, project.id, second_row, 2)

        assert first_created is True
        assert second_created is False
        assert second_task.id == first_task.id
    finally:
        db.close()
