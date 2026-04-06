from datetime import timedelta

from backend.roadmap_engine.storage import goals_repo, matching_repo, roadmap_repo
from backend.roadmap_engine.utils import parse_iso_deadline, utc_today


def _reschedule_dates(total_tasks: int, start_date, end_date) -> list[str]:
    if total_tasks <= 0:
        return []

    available_days = max((end_date - start_date).days + 1, 1)
    if total_tasks == 1:
        return [start_date.isoformat()]

    new_dates: list[str] = []
    for idx in range(total_tasks):
        if available_days == 1:
            day_offset = 0
        else:
            day_offset = int((idx * (available_days - 1)) / (total_tasks - 1))
        new_date = start_date + timedelta(days=day_offset)
        new_dates.append(new_date.isoformat())
    return new_dates


def auto_replan_if_behind(student_id: int) -> dict:
    goal = goals_repo.get_active_goal(student_id)
    if goal is None:
        return {"applied": False, "reason": "no_active_goal"}

    plan = roadmap_repo.get_active_plan(goal["id"])
    if plan is None:
        return {"applied": False, "reason": "no_active_plan"}

    today = utc_today()
    today_iso = today.isoformat()
    overdue_count = roadmap_repo.count_overdue_incomplete(plan["id"], today_iso)
    if overdue_count == 0:
        return {"applied": False, "reason": "on_track"}

    target_end = parse_iso_deadline(goal["target_end_date"]) or today
    if target_end < today:
        target_end = today

    incomplete_tasks = roadmap_repo.list_incomplete_tasks(plan["id"])
    if not incomplete_tasks:
        return {"applied": False, "reason": "no_incomplete_tasks"}

    old_dates = [task["task_date"] for task in incomplete_tasks]
    new_dates = _reschedule_dates(len(incomplete_tasks), today, target_end)

    updates: list[tuple[int, str]] = []
    for task, new_date in zip(incomplete_tasks, new_dates):
        if task["task_date"] != new_date:
            updates.append((task["id"], new_date))

    if not updates:
        return {"applied": False, "reason": "no_change_needed"}

    roadmap_repo.bulk_update_task_dates(updates)
    roadmap_repo.mark_plan_replanned(plan["id"])

    matching_repo.create_notification(
        student_id=student_id,
        goal_id=goal["id"],
        notification_type="roadmap_replanned",
        title="Roadmap Updated",
        body=(
            f"We rescheduled {len(updates)} task(s) because {overdue_count} task(s) were missed."
        ),
    )

    return {
        "applied": True,
        "updated_task_count": len(updates),
        "overdue_task_count": overdue_count,
        "old_start": old_dates[0],
        "new_start": new_dates[0],
    }


def auto_pull_tasks_forward_if_ready(student_id: int) -> dict:
    goal = goals_repo.get_active_goal(student_id)
    if goal is None:
        return {"applied": False, "reason": "no_active_goal"}

    plan = roadmap_repo.get_active_plan(goal["id"])
    if plan is None:
        return {"applied": False, "reason": "no_active_plan"}

    goal_skills = goals_repo.list_goal_skills(goal["id"])
    active_skill = next((item for item in goal_skills if item["status"] != "completed"), None)
    if active_skill is not None and str(active_skill.get("status") or "").strip().lower() != "in_progress":
        goals_repo.set_goal_skill_status(int(active_skill["id"]), "in_progress", None)

    incomplete_tasks = roadmap_repo.list_incomplete_tasks(plan["id"])
    if not incomplete_tasks:
        return {"applied": False, "reason": "no_incomplete_tasks"}

    today = utc_today()
    first_task_date = parse_iso_deadline(incomplete_tasks[0].get("task_date"))
    if first_task_date is None or first_task_date <= today:
        return {"applied": False, "reason": "already_available"}

    target_end = parse_iso_deadline(goal.get("target_end_date")) or today
    if target_end < today:
        target_end = today

    old_dates = [task["task_date"] for task in incomplete_tasks]
    new_dates = _reschedule_dates(len(incomplete_tasks), today, target_end)

    updates: list[tuple[int, str]] = []
    for task, new_date in zip(incomplete_tasks, new_dates):
        if task["task_date"] != new_date:
            updates.append((task["id"], new_date))

    if not updates:
        return {"applied": False, "reason": "no_change_needed"}

    roadmap_repo.bulk_update_task_dates(updates)
    roadmap_repo.mark_plan_replanned(plan["id"])

    try:
        if active_skill is not None:
            from backend.roadmap_engine.services import youtube_learning_service

            youtube_learning_service.get_or_create_recommendations(
                goal_id=int(goal["id"]),
                goal_skill_id=int(active_skill["id"]),
                skill_name=str(active_skill.get("skill_name") or ""),
            )
    except Exception:
        pass

    return {
        "applied": True,
        "updated_task_count": len(updates),
        "old_start": old_dates[0],
        "new_start": new_dates[0],
        "reason": "ahead_of_schedule",
    }
