from datetime import date

from fastapi.testclient import TestClient
from app.database import SessionLocal
from app.main import app
from app.models.baseline_plan import BaselinePlan
from app.models.calculation_profile import CalculationProfile
from app.models.import_batch import ImportBatch
from app.models.import_validation_issue import ImportValidationIssue
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.services.analytics_service import project_contribution


def test_t034_weight_field_recommends_weighted_percent() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T034 权重推荐")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="weight.xlsx", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        db.add_all([
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="A", actual_percent=20, planned_percent=40, weight=2),
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="B", actual_percent=80, planned_percent=60, weight=3),
        ])
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        payload = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id}).json()

    assert payload["calculation_method"] == "weighted_percent"
    assert payload["recommended_method"] == "weighted_percent"
    assert payload["calculation_method_name"] == "权重统计"
    assert payload["weight_sum"] == 5
    assert payload["actual_progress"] == round((20 * 2 + 80 * 3) / 5, 4)
    assert payload["planned_progress"] == round((40 * 2 + 60 * 3) / 5, 4)


def test_t034_value_field_recommends_value_weighted_percent() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T034 产值推荐")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="value.xlsx", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        db.add_all([
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="A", actual_percent=25, planned_percent=50, value_amount=100),
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="B", actual_percent=75, planned_percent=80, value_amount=300),
        ])
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        payload = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id}).json()

    assert payload["calculation_method"] == "value_weighted_percent"
    assert payload["actual_progress"] == round((25 * 100 + 75 * 300) / 400, 4)
    assert payload["planned_progress"] == round((50 * 100 + 80 * 300) / 400, 4)


def test_t034_quantity_recommended_only_when_units_are_consistent() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T034 工程量推荐")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="quantity.xlsx", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        db.add_all([
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="A", unit="米", total_quantity=100, cumulative_quantity=50, planned_percent=40),
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="B", unit="米", total_quantity=300, cumulative_quantity=210, planned_percent=60),
        ])
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        payload = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id}).json()

    assert payload["calculation_method"] == "quantity_percent"
    assert payload["mixed_units"] is False
    assert payload["unit_list"] == ["米"]
    assert payload["actual_progress"] == 65
    assert payload["planned_progress"] == round((40 * 100 + 60 * 300) / 400, 4)


def test_t034_mixed_units_do_not_default_to_quantity_and_show_risk() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T034 单位混杂")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="mixed.xlsx", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        db.add_all([
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="A", unit="米", total_quantity=100, cumulative_quantity=50, actual_percent=50),
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="B", unit="台", total_quantity=10, cumulative_quantity=8, actual_percent=80),
        ])
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        payload = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id}).json()

    quantity = next(method for method in payload["available_methods"] if method["code"] == "quantity_percent")
    assert payload["calculation_method"] == "percent_average"
    assert payload["recommended_method"] != "quantity_percent"
    assert payload["mixed_units"] is True
    assert payload["unit_list"] == ["台", "米"]
    assert quantity["available"] is True
    assert "直接汇总工程量可能失真" in quantity["warning"]


def test_t034_task_average_fallback_when_key_fields_missing() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T034 任务平均 fallback")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="task.xlsx", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        db.add_all([
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="A", status="completed"),
            ProgressItem(project_id=project.id, batch_id=batch.id, task_name="B", status="normal"),
        ])
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        payload = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id}).json()

    assert payload["calculation_method"] == "task_average"
    assert payload["actual_progress"] is None


def test_t030_weighted_normalized_overview_uses_current_range_denominator() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T030 当前范围归一化")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="weight.xlsx", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, discipline="机电", task_name="A", actual_percent=20, planned_percent=50, time_planned_percent=50, weight=0.20),
                ProgressItem(project_id=project.id, batch_id=batch.id, discipline="机电", task_name="B", actual_percent=40, planned_percent=70, time_planned_percent=70, weight=0.2263),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id})

    payload = response.json()
    expected_actual = round((20 * 0.20 + 40 * 0.2263) / 0.4263, 4)
    expected_planned = round((50 * 0.20 + 70 * 0.2263) / 0.4263, 4)
    assert payload["statistics_algorithm"] == "weighted_percent"
    assert payload["statistics_label"] == "权重统计"
    assert payload["is_weight_normalized"] is True
    assert payload["weight_total"] == 0.4263
    assert payload["actual_percent"] == expected_actual
    assert payload["normalized_actual_progress"] == expected_actual
    assert payload["planned_percent"] == expected_planned
    assert payload["normalized_planned_progress"] == expected_planned
    assert payload["project_contribution_actual"] == round(20 * 0.20 + 40 * 0.2263, 4)
    assert payload["project_contribution_planned"] == round(50 * 0.20 + 70 * 0.2263, 4)


def test_t032_project_overview_aggregates_latest_data_date_multi_sheet_batches() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T032 工作台项目级聚合")
        db.add(project)
        db.flush()
        group_id = "t032-group"
        batches = [
            ImportBatch(project_id=project.id, file_name="t032.xlsx", sheet_name="机电单位", import_group_id=group_id, status="published", data_date=date(2026, 5, 18)),
            ImportBatch(project_id=project.id, file_name="t032.xlsx", sheet_name="消防单位", import_group_id=group_id, status="published", data_date=date(2026, 5, 18)),
            ImportBatch(project_id=project.id, file_name="t032.xlsx", sheet_name="智能化单位", import_group_id=group_id, status="published", data_date=date(2026, 5, 18)),
        ]
        db.add_all(batches)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batches[0].id, task_name="机电", actual_percent=20, weight=0.2, planned_start_date=date(2026, 5, 8), planned_finish_date=date(2026, 5, 28)),
                ProgressItem(project_id=project.id, batch_id=batches[1].id, task_name="消防", actual_percent=60, weight=0.3, planned_start_date=date(2026, 5, 8), planned_finish_date=date(2026, 5, 28)),
                ProgressItem(project_id=project.id, batch_id=batches[2].id, task_name="智能化", actual_percent=9.8, weight=0.5, planned_start_date=date(2026, 5, 8), planned_finish_date=date(2026, 5, 28)),
            ]
        )
        db.commit()
        project_id = project.id
        intelligent_batch_id = batches[2].id
    finally:
        db.close()

    with TestClient(app) as client:
        project_overview = client.get(f"/api/projects/{project_id}/analytics/project-overview")
        intelligent_overview = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": intelligent_batch_id})

    assert project_overview.status_code == 200
    payload = project_overview.json()
    expected_actual = round((20 * 0.2 + 60 * 0.3 + 9.8 * 0.5) / 1.0, 4)
    assert payload["is_project_aggregate"] is True
    assert payload["data_date"] == "2026-05-18"
    assert payload["included_batch_count"] == 3
    assert {batch["sheet_name"] for batch in payload["included_batches"]} == {"机电单位", "消防单位", "智能化单位"}
    assert payload["weight_sum"] == 1
    assert payload["project_actual_percent"] == expected_actual
    assert payload["project_planned_percent"] == 50
    assert payload["project_actual_percent"] != intelligent_overview.json()["actual_percent"]
    assert intelligent_overview.json()["actual_percent"] == 9.8


def test_t032_project_overview_aggregates_same_date_without_import_group() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T032 无 group 同日期聚合")
        db.add(project)
        db.flush()
        first = ImportBatch(project_id=project.id, file_name="a.xlsx", sheet_name="机电单位", status="published", data_date=date(2026, 5, 18))
        second = ImportBatch(project_id=project.id, file_name="b.xlsx", sheet_name="消防单位", status="published", data_date=date(2026, 5, 18))
        old = ImportBatch(project_id=project.id, file_name="old.xlsx", sheet_name="旧数据", status="published", data_date=date(2026, 5, 17))
        db.add_all([first, second, old])
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=first.id, task_name="A", actual_percent=10, weight=1, planned_start_date=date(2026, 5, 8), planned_finish_date=date(2026, 5, 28)),
                ProgressItem(project_id=project.id, batch_id=second.id, task_name="B", actual_percent=30, weight=3, planned_start_date=date(2026, 5, 8), planned_finish_date=date(2026, 5, 28)),
                ProgressItem(project_id=project.id, batch_id=old.id, task_name="OLD", actual_percent=100, weight=100, planned_start_date=date(2026, 5, 7), planned_finish_date=date(2026, 5, 27)),
            ]
        )
        db.commit()
        project_id = project.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/project-overview")

    payload = response.json()
    assert payload["included_batch_count"] == 2
    assert payload["project_actual_percent"] == 25
    assert {batch["sheet_name"] for batch in payload["included_batches"]} == {"机电单位", "消防单位"}


def test_t032_project_overview_single_and_empty_states() -> None:
    db = SessionLocal()
    try:
        empty_project = Project(name="T032 空项目")
        single_project = Project(name="T032 单批次")
        db.add_all([empty_project, single_project])
        db.flush()
        batch = ImportBatch(project_id=single_project.id, file_name="single.xlsx", sheet_name="机电单位", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        db.add(ProgressItem(project_id=single_project.id, batch_id=batch.id, task_name="A", actual_percent=80, weight=2, planned_start_date=date(2026, 5, 8), planned_finish_date=date(2026, 5, 28)))
        db.commit()
        empty_project_id = empty_project.id
        single_project_id = single_project.id
    finally:
        db.close()

    with TestClient(app) as client:
        empty_response = client.get(f"/api/projects/{empty_project_id}/analytics/project-overview")
        single_response = client.get(f"/api/projects/{single_project_id}/analytics/project-overview")

    assert empty_response.status_code == 200
    assert empty_response.json()["empty"] is True
    assert empty_response.json()["included_batch_count"] == 0
    assert single_response.status_code == 200
    assert single_response.json()["included_batch_count"] == 1
    assert single_response.json()["project_actual_percent"] == 80
    assert "1 个已发布批次" in single_response.json()["scope_label"]


def test_t030_no_weight_falls_back_to_average() -> None:
    db = SessionLocal()
    try:
        project = Project(name="T030 无权重 fallback")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="noweight.xlsx", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="A", actual_percent=20, planned_percent=40),
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="B", actual_percent=80, planned_percent=60),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id})

    payload = response.json()
    assert payload["statistics_algorithm"] == "percent_average"
    assert payload["actual_percent"] == 50
    assert payload["planned_percent"] == 50
    assert payload["is_weight_normalized"] is False
    assert payload["recommendation_reason"] == "检测到实际完成率字段"


def test_group_algorithm_can_differ_from_overall_algorithm() -> None:
    db = SessionLocal()
    try:
        project = Project(name="算法差异测试")
        db.add(project)
        db.flush()
        profile = CalculationProfile(
            project_id=project.id,
            name="总体平均分组工程量",
            overall_algorithm="avg_percent",
            group_algorithm="quantity_percent",
        )
        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published", data_date=date(2026, 5, 1))
        db.add_all([profile, batch])
        db.flush()
        db.add_all(
            [
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    discipline="电气",
                    unit="米",
                    total_quantity=100,
                    cumulative_quantity=100,
                    actual_quantity=100,
                    actual_percent=100,
                ),
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    discipline="电气",
                    unit="米",
                    total_quantity=300,
                    cumulative_quantity=0,
                    actual_quantity=0,
                    actual_percent=0,
                ),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
        profile_id = profile.id
    finally:
        db.close()

    with TestClient(app) as client:
        overview = client.get(
            f"/api/projects/{project_id}/analytics/overview",
            params={"batch_id": batch_id, "calculation_profile_id": profile_id},
        )
        group = client.get(
            f"/api/projects/{project_id}/analytics/group-by",
            params={"batch_id": batch_id, "calculation_profile_id": profile_id, "dimension": "discipline"},
        )

    assert overview.status_code == 200
    assert group.status_code == 200
    assert overview.json()["actual_percent"] == 50
    assert group.json()["rows"][0]["value"] == 25
    assert group.json()["rows"][0]["units"] == ["米"]


def test_group_by_returns_warning_for_mixed_units_and_falls_back_to_average() -> None:
    db = SessionLocal()
    try:
        project = Project(name="单位混杂测试")
        db.add(project)
        db.flush()
        profile = CalculationProfile(project_id=project.id, name="分组工程量", group_algorithm="quantity_percent")
        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published", data_date=date(2026, 5, 1))
        db.add_all([profile, batch])
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, discipline="机电", unit="米", total_quantity=100, actual_quantity=80, actual_percent=80),
                ProgressItem(project_id=project.id, batch_id=batch.id, discipline="机电", unit="平方米", total_quantity=100, actual_quantity=20, actual_percent=20),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
        profile_id = profile.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/analytics/group-by",
            params={"batch_id": batch_id, "calculation_profile_id": profile_id, "dimension": "discipline"},
        )

    row = response.json()["rows"][0]
    assert row["value"] == 50
    assert row["unit_mixed"] is True
    assert row["warning"]
    assert row["units"] == ["平方米", "米"]


def test_group_by_floor_returns_empty_label_and_natural_order() -> None:
    db = SessionLocal()
    try:
        project = Project(name="楼层统计")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="floor.csv", status="published", data_date=date(2026, 5, 1))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, floor="10层", actual_percent=10, planned_percent=20, progress_deviation=-10),
                ProgressItem(project_id=project.id, batch_id=batch.id, floor="2层", actual_percent=20, planned_percent=20, progress_deviation=0),
                ProgressItem(project_id=project.id, batch_id=batch.id, floor="地下1层", actual_percent=30, planned_percent=None),
                ProgressItem(project_id=project.id, batch_id=batch.id, floor="11层", actual_percent=40, planned_percent=50, progress_deviation=-10),
                ProgressItem(project_id=project.id, batch_id=batch.id, floor="1层", actual_percent=50, planned_percent=60, progress_deviation=-10),
                ProgressItem(project_id=project.id, batch_id=batch.id, floor=None, actual_percent=60),
                ProgressItem(project_id=project.id, batch_id=batch.id, floor="3层", actual_percent=70),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        group_response = client.get(
            f"/api/projects/{project_id}/analytics/group-by",
            params={"batch_id": batch_id, "dimension": "floor"},
        )
        plan_response = client.get(
            f"/api/projects/{project_id}/analytics/plan-vs-actual",
            params={"batch_id": batch_id, "dimension": "floor"},
        )

    assert group_response.status_code == 200
    group_rows = group_response.json()["rows"]
    assert [row["dimension_value"] for row in group_rows] == ["地下1层", "1层", "2层", "3层", "10层", "11层", "未填写楼层"]
    assert group_rows[0]["value"] == 30
    assert group_rows[-1]["dimension_value"] == "未填写楼层"

    plan_rows = plan_response.json()["rows"]
    assert [row["dimension_value"] for row in plan_rows] == ["地下1层", "1层", "2层", "3层", "10层", "11层", "未填写楼层"]
    delayed_by_floor = {row["dimension_value"]: row["delayed_count"] for row in plan_rows}
    assert delayed_by_floor["1层"] == 0
    assert delayed_by_floor["2层"] == 0
    assert delayed_by_floor["10层"] == 0


def test_floor_grouping_does_not_affect_other_dimensions() -> None:
    db = SessionLocal()
    try:
        project = Project(name="维度兼容")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="dimension.csv", status="published", data_date=date(2026, 5, 1))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, building="A座", floor="1层", discipline="机电", system_name="给排水", actual_percent=10),
                ProgressItem(project_id=project.id, batch_id=batch.id, building="B座", floor="2层", discipline="消防", system_name="喷淋", actual_percent=30),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        discipline = client.get(f"/api/projects/{project_id}/analytics/group-by", params={"batch_id": batch_id, "dimension": "discipline"})
        building = client.get(f"/api/projects/{project_id}/analytics/group-by", params={"batch_id": batch_id, "dimension": "building"})
        system = client.get(f"/api/projects/{project_id}/analytics/group-by", params={"batch_id": batch_id, "dimension": "system_name"})

    assert [row["dimension_value"] for row in discipline.json()["rows"]] == ["机电", "消防"]
    assert [row["dimension_value"] for row in building.json()["rows"]] == ["A座", "B座"]
    assert [row["dimension_value"] for row in system.json()["rows"]] == ["喷淋", "给排水"]


def test_building_floor_returns_all_buildings_and_filters_selected_building() -> None:
    db = SessionLocal()
    try:
        project = Project(name="楼栋楼层联动")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="building-floor.csv", status="published", data_date=date(2026, 5, 1))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, building="2号楼", floor="10层", unit="米", actual_percent=20, planned_percent=40, progress_deviation=-20),
                ProgressItem(project_id=project.id, batch_id=batch.id, building="1号楼", floor="地下1层", unit="米", actual_percent=60, planned_percent=70, progress_deviation=-10),
                ProgressItem(project_id=project.id, batch_id=batch.id, building="1号楼", floor="1层", unit="台", actual_percent=80, planned_percent=80, progress_deviation=0),
                ProgressItem(project_id=project.id, batch_id=batch.id, building="1号楼", floor="2层", unit="米", actual_percent=40, planned_percent=60, progress_deviation=-20),
                ProgressItem(project_id=project.id, batch_id=batch.id, building="地下室", floor="B1层", unit="套", actual_percent=50),
                ProgressItem(project_id=project.id, batch_id=batch.id, building="裙楼", floor="屋面", unit="台", actual_percent=30),
                ProgressItem(project_id=project.id, batch_id=batch.id, building="能源中心", floor="管廊", unit="米", actual_percent=90),
                ProgressItem(project_id=project.id, batch_id=batch.id, building="室外", floor="室外", unit="米", actual_percent=10),
                ProgressItem(project_id=project.id, batch_id=batch.id, building=None, floor=None, unit="米", actual_percent=5),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        all_response = client.get(f"/api/projects/{project_id}/analytics/building-floor", params={"batch_id": batch_id})
        one_response = client.get(
            f"/api/projects/{project_id}/analytics/building-floor",
            params={"batch_id": batch_id, "building": "1号楼"},
        )
        floor_response = client.get(f"/api/projects/{project_id}/analytics/group-by", params={"batch_id": batch_id, "dimension": "floor"})
        discipline_response = client.get(f"/api/projects/{project_id}/analytics/group-by", params={"batch_id": batch_id, "dimension": "discipline"})

    assert all_response.status_code == 200
    payload = all_response.json()
    assert payload["buildings"] == ["地下室", "裙楼", "1号楼", "2号楼", "能源中心", "室外", "未填写楼栋"]
    assert ("未填写楼栋", "未填写楼层") in {(row["building"], row["floor"]) for row in payload["items"]}

    assert one_response.status_code == 200
    one_payload = one_response.json()
    assert one_payload["selected_building"] == "1号楼"
    assert {row["building"] for row in one_payload["items"]} == {"1号楼"}
    assert [row["floor"] for row in one_payload["items"]] == ["地下1层", "1层", "2层"]
    delayed_by_floor = {row["floor"]: row["delayed_count"] for row in one_payload["items"]}
    assert delayed_by_floor["地下1层"] == 0
    assert delayed_by_floor["1层"] == 0
    assert delayed_by_floor["2层"] == 0

    rows_by_floor = {row["floor"]: row for row in one_payload["items"]}
    assert rows_by_floor["1层"]["actual_percent"] == 80
    assert rows_by_floor["1层"]["planned_percent"] == 80

    assert floor_response.status_code == 200
    assert discipline_response.status_code == 200


def test_building_floor_returns_project_not_found_code_for_missing_project() -> None:
    with TestClient(app) as client:
        response = client.get("/api/projects/999999/analytics/building-floor")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


def test_requested_baseline_does_not_hide_items_without_baseline_for_floor_stats() -> None:
    db = SessionLocal()
    try:
        project = Project(name="无基线楼层统计")
        db.add(project)
        db.flush()
        baseline = BaselinePlan(project_id=project.id, name="默认计划", is_default=True)
        db.add(baseline)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="floor.csv", status="published", data_date=date(2026, 5, 1))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, building="A1", floor="1层", actual_percent=10),
                ProgressItem(project_id=project.id, batch_id=batch.id, building="A1", floor="2层", actual_percent=20),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
        baseline_id = baseline.id
    finally:
        db.close()

    with TestClient(app) as client:
        floor_response = client.get(
            f"/api/projects/{project_id}/analytics/group-by",
            params={"batch_id": batch_id, "dimension": "floor", "baseline_plan_id": baseline_id},
        )
        building_floor_response = client.get(
            f"/api/projects/{project_id}/analytics/building-floor",
            params={"batch_id": batch_id, "baseline_plan_id": baseline_id},
        )

    assert floor_response.status_code == 200
    assert [row["dimension_value"] for row in floor_response.json()["rows"]] == ["1层", "2层"]
    assert building_floor_response.status_code == 200
    assert [row["floor"] for row in building_floor_response.json()["items"]] == ["1层", "2层"]


def test_weighted_group_algorithm_calculates_weighted_percent() -> None:
    db = SessionLocal()
    try:
        project = Project(name="权重测试")
        db.add(project)
        db.flush()
        profile = CalculationProfile(project_id=project.id, name="分组权重", group_algorithm="weighted_percent")
        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published", data_date=date(2026, 5, 1))
        db.add_all([profile, batch])
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, discipline="电气", unit="米", actual_percent=100, weight=1),
                ProgressItem(project_id=project.id, batch_id=batch.id, discipline="电气", unit="米", actual_percent=50, weight=3),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
        profile_id = profile.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/analytics/group-by",
            params={"batch_id": batch_id, "calculation_profile_id": profile_id, "dimension": "discipline"},
        )

    assert response.json()["rows"][0]["value"] == 62.5


def test_analytics_filters_by_requested_or_batch_default_baseline() -> None:
    db = SessionLocal()
    try:
        project = Project(name="基线过滤测试")
        db.add(project)
        db.flush()
        baseline_a = BaselinePlan(project_id=project.id, name="当前计划", is_default=True)
        baseline_b = BaselinePlan(project_id=project.id, name="调整计划")
        db.add_all([baseline_a, baseline_b])
        db.flush()
        batch = ImportBatch(
            project_id=project.id,
            file_name="a.csv",
            status="published",
            data_date=date(2026, 5, 1),
            baseline_plan_id=baseline_a.id,
        )
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, baseline_plan_id=baseline_a.id, task_name="A", actual_percent=80),
                ProgressItem(project_id=project.id, batch_id=batch.id, baseline_plan_id=baseline_b.id, task_name="B", actual_percent=20),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
        baseline_a_id = baseline_a.id
        baseline_b_id = baseline_b.id
    finally:
        db.close()

    with TestClient(app) as client:
        default_response = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id})
        requested_response = client.get(
            f"/api/projects/{project_id}/analytics/overview",
            params={"batch_id": batch_id, "baseline_plan_id": baseline_b_id},
        )

    assert default_response.json()["baseline_plan_id"] == baseline_a_id
    assert default_response.json()["batch_bound_baseline_plan_id"] == baseline_a_id
    assert default_response.json()["current_view_baseline_plan_id"] == baseline_a_id
    assert default_response.json()["baseline_consistent"] is True
    assert default_response.json()["baseline_notice"] == "当前批次采用计划基线：当前计划。"
    assert default_response.json()["item_count"] == 1
    assert default_response.json()["actual_percent"] == 80
    assert requested_response.json()["baseline_plan_id"] == baseline_b_id
    assert requested_response.json()["batch_bound_baseline_plan_id"] == baseline_a_id
    assert requested_response.json()["current_view_baseline_plan_id"] == baseline_b_id
    assert requested_response.json()["baseline_consistent"] is False
    assert requested_response.json()["baseline_notice"] == "当前查看基线与批次绑定基线不同，请注意分析口径。"
    assert requested_response.json()["item_count"] == 1
    assert requested_response.json()["actual_percent"] == 20


def test_baseline_comparison_returns_bound_and_current_context() -> None:
    db = SessionLocal()
    try:
        project = Project(name="基线对比测试")
        db.add(project)
        db.flush()
        bound = BaselinePlan(project_id=project.id, name="5月总控计划", is_default=True)
        current = BaselinePlan(project_id=project.id, name="5月调整计划")
        db.add_all([bound, current])
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="fire.xlsx", sheet_name="消防单位", status="published", data_date=date(2026, 5, 12), baseline_plan_id=bound.id)
        db.add(batch)
        db.commit()
        project_id = project.id
        batch_id = batch.id
        current_id = current.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/analytics/baseline-comparison",
            params={"batch_id": batch_id, "baseline_plan_id": current_id},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch_bound_baseline_plan_name"] == "5月总控计划"
    assert payload["current_view_baseline_plan_name"] == "5月调整计划"
    assert payload["is_consistent"] is False
    assert payload["notice"] == "当前查看基线与批次绑定基线不同，请注意分析口径。"


def test_overview_returns_progress_values_without_baseline_plan() -> None:
    db = SessionLocal()
    try:
        project = Project(name="无基线进度计算")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published", data_date=date(2026, 5, 1))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="A", actual_percent=40, planned_percent=60, progress_deviation=-20),
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="B", actual_percent=80, planned_percent=90, progress_deviation=-10),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id})

    assert response.status_code == 200
    assert response.json()["baseline_plan_id"] is None
    assert response.json()["actual_percent"] == 60
    assert response.json()["planned_percent"] == 75
    assert response.json()["progress_deviation"] == -15


def test_overview_averages_only_items_with_actual_percent() -> None:
    db = SessionLocal()
    try:
        project = Project(name="部分可计算进度")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published", data_date=date(2026, 5, 1))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="A", actual_percent=20),
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="B", actual_percent=None),
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="C", actual_percent=80),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id})

    assert response.status_code == 200
    assert response.json()["actual_percent"] == 50


def test_overview_warns_when_progress_is_not_calculable_and_quality_is_low() -> None:
    db = SessionLocal()
    try:
        project = Project(name="不可计算进度提示")
        db.add(project)
        db.flush()
        batch = ImportBatch(
            project_id=project.id,
            file_name="bad.csv",
            status="published",
            data_date=date(2026, 5, 1),
            data_quality_score=57.5,
        )
        db.add(batch)
        db.flush()
        db.add(ProgressItem(project_id=project.id, batch_id=batch.id, task_name="只有任务名", discipline="机电"))
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["actual_percent"] is None
    assert payload["planned_percent"] is None
    codes = {warning["code"] for warning in payload["warnings"]}
    assert {"no_calculable_progress", "no_calculable_actual_progress", "no_calculable_planned_progress", "low_data_quality"} <= codes


def test_delayed_ranking_uses_current_batch_when_baseline_plan_is_absent() -> None:
    db = SessionLocal()
    try:
        project = Project(name="无基线滞后排行")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published", data_date=date(2026, 5, 1))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    task_name="喷淋系统",
                    building="A1",
                    floor="3层",
                    discipline="消防",
                    system_name="喷淋系统",
                    unit="项",
                    actual_percent=58,
                    planned_percent=69,
                    progress_deviation=-11,
                    planned_start_date=date(2026, 4, 1),
                    planned_finish_date=date(2026, 5, 1),
                    status="seriously_delayed",
                ),
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    task_name="轻微滞后",
                    actual_percent=80,
                    planned_percent=83,
                    progress_deviation=-3,
                    planned_start_date=date(2026, 4, 1),
                    planned_finish_date=date(2026, 5, 1),
                    status="slightly_delayed",
                ),
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="正常", actual_percent=100, planned_percent=80, progress_deviation=0, planned_start_date=date(2026, 4, 1), planned_finish_date=date(2026, 5, 1), status="completed"),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/delayed-ranking", params={"batch_id": batch_id})

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert [row["task_name"] for row in rows] == ["喷淋系统", "轻微滞后"]
    assert [row["progress_deviation"] for row in rows] == [-42, -20]

    serious = rows[0]
    assert serious["id"] == serious["progress_item_id"]
    assert serious["building"] == "A1"
    assert serious["floor"] == "3层"
    assert serious["discipline"] == "消防"
    assert serious["system_name"] == "喷淋系统"
    assert serious["unit"] == "项"
    assert serious["delay_level"] == "seriously_delayed"
    assert serious["delay_level_label"] == "严重滞后"
    assert "【消防】A1 3层 喷淋系统" in serious["delay_message"]
    assert "滞后 42.0 个百分点" in serious["delay_message"]

    minor = rows[1]
    assert minor["building"] == "未填写楼栋"
    assert minor["floor"] == "未填写楼层"
    assert minor["discipline"] == "未填写专业"
    assert minor["system_name"] == "未填写系统"
    assert minor["delay_level"] == "delayed"
    assert minor["delay_level_label"] == "明显滞后"
    assert "未填写楼栋" not in minor["delay_message"]


def test_delayed_ranking_excludes_items_before_plan_start() -> None:
    db = SessionLocal()
    try:
        project = Project(name="计划开始未到滞后排行")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="a.csv", status="published", data_date=date(2026, 5, 18))
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    task_name="未到计划开始",
                    total_quantity=100,
                    cumulative_quantity=0,
                    actual_percent=0,
                    planned_percent=40,
                    progress_deviation=-40,
                    planned_start_date=date(2026, 5, 20),
                    planned_finish_date=date(2026, 5, 30),
                    status="not_started_by_plan",
                ),
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    task_name="已到计划开始",
                    total_quantity=100,
                    cumulative_quantity=0,
                    actual_percent=0,
                    planned_percent=40,
                    progress_deviation=-40,
                    planned_start_date=date(2026, 5, 1),
                    planned_finish_date=date(2026, 5, 31),
                    status="seriously_delayed",
                ),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/delayed-ranking", params={"batch_id": batch_id})

    assert response.status_code == 200
    assert [row["task_name"] for row in response.json()["rows"]] == ["已到计划开始"]


def test_data_quality_returns_validation_issue_code_counts() -> None:
    db = SessionLocal()
    try:
        project = Project(name="校验分布")
        db.add(project)
        db.flush()
        batch = ImportBatch(
            project_id=project.id,
            file_name="a.csv",
            status="published",
            data_date=date(2026, 5, 1),
            data_quality_score=65,
            warning_count=3,
            error_count=1,
        )
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ImportValidationIssue(batch_id=batch.id, level="warning", code="INVALID_DATE", message="bad date"),
                ImportValidationIssue(batch_id=batch.id, level="warning", code="INVALID_DATE", message="bad date"),
                ImportValidationIssue(batch_id=batch.id, level="warning", code="UNIT_MIXED", message="mixed"),
                ImportValidationIssue(batch_id=batch.id, level="error", code="invalid_percent", message="bad percent"),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/data-quality", params={"batch_id": batch_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_quality_score"] == 65
    assert payload["warning_count"] == 3
    assert payload["error_count"] == 1
    counts = {(item["code"], item["level"]): item["count"] for item in payload["issue_code_counts"]}
    assert counts[("INVALID_DATE", "warning")] == 2
    assert counts[("UNIT_MIXED", "warning")] == 1
    assert counts[("invalid_percent", "error")] == 1


def test_insight_returns_rule_based_progress_summary_and_delays() -> None:
    db = SessionLocal()
    try:
        project = Project(name="进度分析")
        db.add(project)
        db.flush()
        batch = ImportBatch(
            project_id=project.id,
            file_name="insight.xlsx",
            status="published",
            data_date=date(2026, 5, 12),
            warning_count=1,
            error_count=0,
            data_quality_score=92,
        )
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="喷淋系统", building="A1", floor="3层", discipline="消防", unit="项", actual_percent=50, planned_percent=70, progress_deviation=-20, planned_start_date=date(2026, 4, 1), planned_finish_date=date(2026, 5, 1), status="seriously_delayed"),
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="风管安装", building="A1", floor="4层", discipline="暖通", unit="米", actual_percent=60, planned_percent=72, progress_deviation=-12, planned_start_date=date(2026, 4, 1), planned_finish_date=date(2026, 5, 1), status="seriously_delayed"),
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="桥架安装", building="A2", floor="2层", discipline="智能化", unit="米", actual_percent=80, planned_percent=90, progress_deviation=-10, planned_start_date=date(2026, 4, 1), planned_finish_date=date(2026, 5, 1), status="delayed"),
            ]
        )
        db.add(ImportValidationIssue(batch_id=batch.id, level="warning", code="INVALID_DATE", message="bad date"))
        db.add(ImportValidationIssue(batch_id=batch.id, level="warning", code="SUMMARY_ROW_SKIPPED", message="skip"))
        db.add(ImportValidationIssue(batch_id=batch.id, level="warning", code="negative_quantity", message="negative"))
        db.add(ImportValidationIssue(batch_id=batch.id, level="warning", code="percent_out_of_range", message="bad percent"))
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/insight", params={"batch_id": batch_id})

    assert response.status_code == 200
    payload = response.json()
    assert "截至 2026-05-12" in payload["overview_summary"]
    assert "实际完成率" in payload["overview_summary"]
    assert "本期共纳入 3 项进度任务" in payload["overview_summary"]
    assert "数据质量评分为 92.0 分" in payload["overview_summary"]
    assert "整体进度明显滞后" in payload["overview_summary"]
    assert "消防" in payload["discipline_summary"]
    assert "建议作为本期协调重点" in payload["discipline_summary"]
    assert "3层" in payload["floor_summary"]
    assert "材料供应和专业穿插" in payload["floor_summary"]
    assert "A1 3层" in payload["building_floor_summary"]
    assert "整改跟踪的重点区域" in payload["building_floor_summary"]
    assert "喷淋系统" in payload["delay_summary"]
    assert "建议优先跟踪" in payload["delay_summary"]
    assert "数据质量较好" in payload["quality_summary"]
    assert "日期格式异常" in payload["quality_summary"]
    assert "自动跳过合计" in payload["quality_summary"]
    assert "工程量为负数" in payload["quality_summary"]
    assert "完成率超出 0-100" in payload["quality_summary"]
    assert 1 <= len(payload["focus_points"]) <= 5
    assert 1 <= len(payload["recommended_actions"]) <= 5


def test_insight_reports_missing_plan_and_no_delayed_items() -> None:
    db = SessionLocal()
    try:
        project = Project(name="无计划分析")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="actual.xlsx", status="published", data_date=date(2026, 5, 12), data_quality_score=80)
        db.add(batch)
        db.flush()
        db.add(ProgressItem(project_id=project.id, batch_id=batch.id, task_name="已完成项", floor="1层", discipline="机电", actual_percent=88))
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/insight", params={"batch_id": batch_id})

    assert response.status_code == 200
    payload = response.json()
    assert "缺少计划进度字段" in payload["overview_summary"]
    assert "计划基线数据" in payload["overview_summary"]
    assert "暂无法生成分专业滞后判断" in payload["discipline_summary"]
    assert payload["delay_summary"] == "当前批次暂无滞后项。"
    assert "数据质量一般" in payload["quality_summary"]


def test_insight_quality_summary_uses_high_middle_and_low_thresholds() -> None:
    db = SessionLocal()
    try:
        project = Project(name="质量阈值")
        db.add(project)
        db.flush()
        batches = []
        for score in (90, 70, 50):
            batch = ImportBatch(project_id=project.id, file_name=f"{score}.xlsx", status="published", data_date=date(2026, 5, 12), data_quality_score=score)
            db.add(batch)
            db.flush()
            db.add(ProgressItem(project_id=project.id, batch_id=batch.id, task_name="任务", actual_percent=50, planned_percent=50, progress_deviation=0))
            batches.append(batch.id)
        db.commit()
        project_id = project.id
    finally:
        db.close()

    with TestClient(app) as client:
        summaries = [
            client.get(f"/api/projects/{project_id}/analytics/insight", params={"batch_id": batch_id}).json()["quality_summary"]
            for batch_id in batches
        ]

    assert "数据质量较好" in summaries[0]
    assert "数据质量一般" in summaries[1]
    assert "数据质量偏低" in summaries[2]


def test_insight_reports_missing_actual_progress() -> None:
    db = SessionLocal()
    try:
        project = Project(name="无实际")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="empty.xlsx", status="published", data_date=date(2026, 5, 12))
        db.add(batch)
        db.flush()
        db.add(ProgressItem(project_id=project.id, batch_id=batch.id, task_name="任务", planned_percent=50))
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/insight", params={"batch_id": batch_id})

    assert response.status_code == 200
    assert "缺少可计算的实际进度字段" in response.json()["overview_summary"]


def test_insight_reports_no_delayed_discipline_and_missing_floor_data() -> None:
    db = SessionLocal()
    try:
        project = Project(name="无滞后")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="normal.xlsx", status="published", data_date=date(2026, 5, 12), data_quality_score=88)
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="任务1", discipline="机电", actual_percent=80, planned_percent=70, progress_deviation=10),
                ProgressItem(project_id=project.id, batch_id=batch.id, task_name="任务2", discipline="消防", actual_percent=90, planned_percent=90, progress_deviation=0),
            ]
        )
        db.commit()
        project_id = project.id
        batch_id = batch.id
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/analytics/insight", params={"batch_id": batch_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["discipline_summary"] == "当前分专业进度暂无明显滞后。"
    assert payload["floor_summary"] == "当前批次暂无楼层统计数据，建议检查字段映射中是否包含楼层字段。"
    assert payload["delay_summary"] == "当前批次暂无滞后项。"
    assert len(payload["focus_points"]) <= 5
    assert len(payload["recommended_actions"]) <= 5
