import copy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.database import Base, VideoProject, VideoSourceBlock
from backend.services import video_longform_workflow as workflow
from backend.services.video_longform import LongFormPlanningError, generate_chapters, validate_outline
from backend.services.video_planning import VideoPlanningValidationError


def _outline():
    return {
        "central_question": "Vì sao?",
        "central_promise": "Bạn sẽ hiểu cách làm.",
        "payoff": "Có thể áp dụng.",
        "chapters": [
            {
                "order": 1,
                "title": "Mở",
                "goal": "Đặt vấn đề",
                "duration_seconds": 30,
                "state_in": "start",
                "state_out": "problem",
                "bridge": "Tìm nguyên nhân",
            },
            {
                "order": 2,
                "title": "Kết",
                "goal": "Giải quyết",
                "duration_seconds": 30,
                "state_in": "problem",
                "state_out": "solved",
                "bridge": "Chốt cách làm",
            },
        ],
    }


def test_validate_outline_rejects_broken_continuity():
    value = _outline()
    value["chapters"][1]["state_in"] = "other"
    with pytest.raises(LongFormPlanningError):
        validate_outline(value, 60)


def test_generate_chapters_resumes_completed_prefix_and_checkpoints():
    calls = []
    checkpoints = []

    def run(prompt, schema, step):
        calls.append(step)
        order = 2 if step.endswith("2") else 1
        return {
            "narration": f"Nội dung chương {order} mới và khác biệt đủ dài.",
            "state_out": "solved",
            "bridge": "Kết luận",
            "review_vi": "Ổn",
            "scenes": [{"title": "S", "english_narration": "N"}],
        }

    result = generate_chapters(
        _outline(),
        "context",
        run,
        completed_chapters=[
            {**_outline()["chapters"][0], "narration": "Đã viết chương một.", "scenes": [{"title": "S"}]}
        ],
        on_chapter=lambda value: checkpoints.append(len(value)),
    )
    assert calls == ["longform_chapter_2"]
    assert checkpoints == [2]
    assert result["status"] == "ready_for_editorial_review"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as session:
        yield session
    engine.dispose()


def _project(db):
    project = VideoProject(
        id="longform",
        title="Longform",
        topic="Topic",
        phase="phase2",
        target_language="vi",
        format_profile="long_form",
        target_duration_seconds=60,
    )
    db.add(project)
    db.commit()
    return project


def _runner(calls, *, fail_step=None, review_passed=True):
    def run(_prompt, _schema, step):
        calls.append(step)
        if step == fail_step:
            raise RuntimeError("Planning interrupted")
        if step == "longform_outline":
            return _outline()
        if step == "longform_editorial_review":
            return {
                "passed": review_passed,
                "blocking_errors": [] if review_passed else ["Missing payoff"],
                "warnings": [],
                "recommended_actions": [],
            }
        order = int(step.rsplit("_", 1)[1])
        narration = (
            "Ta mở đầu bằng câu hỏi về hiện tượng." if order == 1 else "Giải pháp này dựa vào kết quả thí nghiệm mới."
        )
        return {
            "narration": narration,
            "state_out": "problem" if order == 1 else "solved",
            "bridge": "Tìm nguyên nhân" if order == 1 else "Chốt cách làm",
            "review_vi": narration,
            "scenes": [{"title": f"Scene {order}", "english_narration": narration}],
        }

    return run


def _approved_outline(project, db):
    assert workflow.develop(project, db, "Context", _runner([])) is None
    revision = workflow.state(project)["revision"]
    workflow.approve_outline(project.id, True, db, expected_revision=revision)
    return revision


def test_workflow_requires_approval_and_editorial_pass_then_persists_readiness(db):
    project = _project(db)
    calls = []
    run = _runner(calls)
    assert workflow.develop(project, db, "Context", run) is None
    assert calls == ["longform_outline"]
    assert workflow.develop(project, db, "Context", run) is None
    assert calls == ["longform_outline"]  # No chapter is generated before approval.
    with pytest.raises(VideoPlanningValidationError):
        workflow.require_ready(project, db)
    workflow.approve_outline(project.id, True, db, expected_revision=1)
    plan = workflow.develop(project, db, "Context", run)
    assert calls == ["longform_outline", "longform_chapter_1", "longform_chapter_2", "longform_editorial_review"]
    assert len(plan["scenes"]) == 2
    with Session(db.bind, autoflush=False) as reopened:
        stored = reopened.get(VideoProject, project.id)
        assert workflow.state(stored)["outline_approved"] is True
        assert workflow.state(stored)["status"] == "ready"
        workflow.require_ready(stored, reopened)


def test_stale_outline_revision_cannot_be_approved_or_edited(db):
    project = _project(db)
    revision = _approved_outline(project, db)
    workflow.update_outline(project.id, _outline(), db, expected_revision=revision)
    for action in (
        lambda: workflow.approve_outline(project.id, True, db, expected_revision=revision),
        lambda: workflow.update_outline(project.id, _outline(), db, expected_revision=revision),
    ):
        with pytest.raises(VideoPlanningValidationError, match="Dàn ý đã thay đổi"):
            action()
    assert workflow.state(project)["revision"] == revision + 1
    assert workflow.state(project)["outline_approved"] is False


@pytest.mark.parametrize("change", ["topic", "source"])
def test_changed_input_revokes_old_readiness_and_rebuilds_outline(db, change):
    project = _project(db)
    _approved_outline(project, db)
    workflow.develop(project, db, "Context", _runner([]))
    if change == "topic":
        project.topic = "Changed topic"
    else:
        db.add(VideoSourceBlock(project_id=project.id, block_type="idea", content="New input"))
    db.commit()
    with pytest.raises(VideoPlanningValidationError):
        workflow.require_ready(project, db)
    with pytest.raises(VideoPlanningValidationError, match="Đầu vào đã thay đổi"):
        workflow.approve_outline(project.id, True, db, expected_revision=1)
    calls = []
    assert workflow.develop(project, db, "New context", _runner(calls)) is None
    assert calls == ["longform_outline"]
    assert workflow.state(project)["revision"] == 2
    assert workflow.state(project)["outline_approved"] is False
    assert workflow.state(project)["chapters"] == []


def test_interrupted_chapter_is_resumed_from_persisted_checkpoint_after_reopening(db):
    project = _project(db)
    _approved_outline(project, db)
    with pytest.raises(RuntimeError, match="interrupted"):
        workflow.develop(project, db, "Context", _runner([], fail_step="longform_chapter_2"))
    assert workflow.state(project)["status"] == "blocked"
    assert len(workflow.state(project)["chapters"]) == 1
    calls = []
    with Session(db.bind, autoflush=False) as restarted:
        stored = restarted.get(VideoProject, project.id)
        assert workflow.state(stored)["outline_approved"] is True
        plan = workflow.develop(stored, restarted, "Context", _runner(calls))
        workflow.require_ready(stored, restarted)
    assert calls == ["longform_chapter_2", "longform_editorial_review"]
    assert len(plan["scenes"]) == 2


def test_failed_editorial_review_blocks_production_and_retry_reuses_chapters(db):
    project = _project(db)
    _approved_outline(project, db)
    with pytest.raises(VideoPlanningValidationError, match="biên tập chưa đạt"):
        workflow.develop(project, db, "Context", _runner([], review_passed=False))
    with pytest.raises(VideoPlanningValidationError):
        workflow.require_ready(project, db)
    assert workflow.state(project)["editorial_review"]["passed"] is False
    calls = []
    workflow.develop(project, db, "Context", _runner(calls))
    assert calls == ["longform_editorial_review"]
    workflow.require_ready(project, db)


@pytest.mark.parametrize("change", ["revision", "source"])
def test_late_ai_response_does_not_overwrite_a_newer_outline_or_input(db, change):
    project = _project(db)
    _approved_outline(project, db)
    run = _runner([])
    newer_state = None

    def concurrent_run(prompt, schema, step):
        nonlocal newer_state
        if step == "longform_chapter_1":
            with Session(db.bind, autoflush=False) as other:
                newer = other.get(VideoProject, project.id)
                value = workflow.state(newer)
                if change == "revision":
                    value.update(revision=2, status="outline_ready", outline_approved=False, chapters=[])
                    newer.retention_plan_json = {"longform": value}
                else:
                    other.add(VideoSourceBlock(project_id=project.id, block_type="idea", content="Concurrent input"))
                other.commit()
                newer_state = copy.deepcopy(workflow.state(newer))
        return run(prompt, schema, step)

    with pytest.raises(VideoPlanningValidationError, match="đã thay đổi trong khi AI chạy"):
        workflow.develop(project, db, "Context", concurrent_run)
    db.refresh(project)
    assert workflow.state(project) == newer_state
    assert workflow.state(project)["chapters"] == []


def test_approval_lock_is_released_after_interruption(db):
    project = _project(db)
    _approved_outline(project, db)

    def interrupted():
        with workflow.planning(project.id):
            with pytest.raises(VideoPlanningValidationError, match="đang được xử lý"):
                workflow.approve_outline(project.id, False, db, expected_revision=1)
            raise RuntimeError("Interrupted")

    with pytest.raises(RuntimeError):
        interrupted()
    workflow.approve_outline(project.id, False, db, expected_revision=1)
    assert workflow.state(project)["outline_approved"] is False
