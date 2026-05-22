import json
from datetime import date

from app.database import SessionLocal
from app.models.baseline_plan import BaselinePlan
from app.models.baseline_plan_snapshot import BaselinePlanSnapshot
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.services.baseline_snapshot_service import (
    compute_snapshot_diff,
    create_snapshot,
    list_snapshots,
)


def _make_baseline_with_items(item_specs: list[dict]) -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        project = Project(name="快照测试项目")
        db.add(project)
        db.flush()
        baseline = BaselinePlan(project_id=project.id, name="2026-Q2 基线", is_default=True)
        db.add(baseline)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="plan.xlsx", baseline_plan_id=baseline.id, status="published")
        db.add(batch)
        db.flush()
        for spec in item_specs:
            db.add(
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    baseline_plan_id=baseline.id,
                    identity_key=spec["identity"],
                    task_name=spec["identity"],
                    discipline=spec.get("discipline", "电气"),
                    planned_start_date=spec.get("planned_start_date"),
                    planned_finish_date=spec.get("planned_finish_date"),
                    planned_percent=spec.get("planned_percent"),
                    imported_planned_percent=spec.get("planned_percent"),
                    actual_percent=spec.get("actual_percent"),
                )
            )
        db.commit()
        return project.id, baseline.id, batch.id
    finally:
        db.close()


def test_create_snapshot_freezes_current_plan_payload() -> None:
    _, baseline_id, _ = _make_baseline_with_items(
        [
            {
                "identity": "电气-1F-桥架",
                "planned_start_date": date(2026, 3, 1),
                "planned_finish_date": date(2026, 4, 1),
                "planned_percent": 50.0,
                "actual_percent": 30.0,
            },
            {
                "identity": "电气-2F-桥架",
                "planned_start_date": date(2026, 3, 15),
                "planned_finish_date": date(2026, 4, 15),
                "planned_percent": 40.0,
                "actual_percent": 20.0,
            },
        ]
    )
    db = SessionLocal()
    try:
        baseline_db = db.get(BaselinePlan, baseline_id)
        snapshot = create_snapshot(db, baseline_db, label="初版基线快照")
        db.commit()
        db.refresh(snapshot)
        assert snapshot.item_count == 2
        data = json.loads(snapshot.payload)
        identities = sorted(item["identity"] for item in data["items"])
        assert identities == ["电气-1F-桥架", "电气-2F-桥架"]
        first = next(item for item in data["items"] if item["identity"] == "电气-1F-桥架")
        assert first["plan"]["planned_percent"] == 50.0
        assert first["plan"]["planned_start_date"] == "2026-03-01"
        assert first["actual"]["actual_percent"] == 30.0
    finally:
        db.close()


def test_list_snapshots_orders_newest_first() -> None:
    _, baseline_id, _ = _make_baseline_with_items([{"identity": "X"}])
    db = SessionLocal()
    try:
        baseline_db = db.get(BaselinePlan, baseline_id)
        create_snapshot(db, baseline_db, label="老快照", snapshot_date=date(2026, 1, 1))
        create_snapshot(db, baseline_db, label="新快照", snapshot_date=date(2026, 4, 1))
        db.commit()
        snapshots = list_snapshots(db, baseline_id)
        assert [s.label for s in snapshots] == ["新快照", "老快照"]
    finally:
        db.close()


def test_compute_snapshot_diff_reports_added_removed_and_changed() -> None:
    project_id, baseline_id, batch_id = _make_baseline_with_items(
        [
            {
                "identity": "电气-1F-桥架",
                "planned_finish_date": date(2026, 4, 1),
                "planned_percent": 50.0,
                "actual_percent": 30.0,
            },
            {
                "identity": "电气-2F-桥架",
                "planned_finish_date": date(2026, 4, 15),
                "planned_percent": 40.0,
                "actual_percent": 20.0,
            },
        ]
    )
    db = SessionLocal()
    try:
        baseline_db = db.get(BaselinePlan, baseline_id)
        snapshot = create_snapshot(db, baseline_db, label="基准快照")
        db.commit()
        snapshot_id = snapshot.id

        # Mutate progress items: change planned_finish_date for 1F, remove 2F, add 3F
        item_1f_row = db.query(ProgressItem).filter(ProgressItem.identity_key == "电气-1F-桥架").one()
        item_1f_row.planned_finish_date = date(2026, 5, 1)
        item_1f_row.actual_percent = 60.0
        item_2f_row = db.query(ProgressItem).filter(ProgressItem.identity_key == "电气-2F-桥架").one()
        db.delete(item_2f_row)
        db.add(
            ProgressItem(
                project_id=project_id,
                batch_id=batch_id,
                baseline_plan_id=baseline_id,
                identity_key="电气-3F-桥架",
                task_name="电气-3F-桥架",
                discipline="电气",
                planned_percent=20.0,
            )
        )
        db.commit()

        snapshot_db = db.get(BaselinePlanSnapshot, snapshot_id)
        diff = compute_snapshot_diff(db, snapshot_db)
    finally:
        db.close()

    assert diff["added_count"] == 1
    assert diff["removed_count"] == 1
    assert diff["changed_count"] == 1
    assert diff["added"][0]["identity"] == "电气-3F-桥架"
    assert diff["removed"][0]["identity"] == "电气-2F-桥架"
    changed = diff["changed"][0]
    assert changed["identity"] == "电气-1F-桥架"
    assert "planned_finish_date" in changed["plan_changes"]
    assert changed["plan_changes"]["planned_finish_date"]["before"] == "2026-04-01"
    assert changed["plan_changes"]["planned_finish_date"]["after"] == "2026-05-01"
    assert "actual_percent" in changed["actual_changes"]
