import unittest
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from workload import (
    calculate_outstanding_hours,
    calculate_available_hours,
    group_tasks_by_deadline,
    calculate_hours_due_by,
    check_deadline_conflicts,
    get_upcoming_deadlines,
    calculate_utilization,
    get_employee_workload_summary,
    get_team_workload_summary
)

TODAY = date(2026, 11, 2)  # Monday; fixed date keeps tests deterministic

def make_task(hours, days_until_due, status='Active', employee_id=1):
    return {
        'estimated_hours': hours,
        'deadline': (TODAY + timedelta(days=days_until_due)).isoformat(),
        'status': status,
        "employee_id": employee_id
    }


class TestOutstandingHours(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(calculate_outstanding_hours([]), 0)

    def test_active_tasks_are_summed(self):
        self.assertEqual(calculate_outstanding_hours([make_task(12, 3), make_task(6, 8)]), 18)

    def test_completed_tasks_are_excluded(self):
        tasks = [make_task(12, 3), make_task(10, 4, 'Completed')]
        self.assertEqual(calculate_outstanding_hours(tasks), 12)

    def test_all_completed(self):
        self.assertEqual(calculate_outstanding_hours([make_task(7, 2, 'Completed')]), 0)

    def test_fractional_hours(self):
        self.assertAlmostEqual(calculate_outstanding_hours([make_task(1.5, 1), make_task(2.25, 2)]), 3.75)

    def test_overdue_active_tasks_are_included(self):
        tasks = [make_task(5, -3), make_task(7, 10)]
        self.assertEqual(calculate_outstanding_hours(tasks),12)


class TestAvailableHours(unittest.TestCase):
    def test_full_workweek(self):
        self.assertEqual(calculate_available_hours(40, TODAY, TODAY + timedelta(days=4)), 40)

    def test_two_workweeks(self):
        self.assertEqual(calculate_available_hours(40, TODAY, TODAY + timedelta(days=13)), 80)

    def test_partial_week(self):
        self.assertEqual(calculate_available_hours(30, TODAY, TODAY + timedelta(days=2)), 18)

    def test_weekend_only(self):
        saturday = TODAY + timedelta(days=5)
        sunday = TODAY + timedelta(days=6)
        self.assertEqual(calculate_available_hours(40, saturday, sunday), 0)

    def test_single_weekday_is_inclusive(self):
        self.assertEqual(calculate_available_hours(40, TODAY, TODAY), 8)

    def test_single_weekend_day(self):
        saturday = TODAY + timedelta(days=5)
        self.assertEqual(calculate_available_hours(40, saturday, saturday), 0)

    def test_reversed_date_range(self):
        self.assertEqual(calculate_available_hours(40, TODAY + timedelta(days=1), TODAY), 0)

    def test_zero_weekly_hours(self):
        self.assertEqual(calculate_available_hours(0, TODAY, TODAY + timedelta(days=13)), 0)

    def test_negative_weekly_hours(self):
        with self.assertRaises(ValueError):
            calculate_available_hours(-1, TODAY, TODAY + timedelta(days=1))

    def test_fractional_daily_hours(self):
        self.assertAlmostEqual(calculate_available_hours(37.5, TODAY, TODAY + timedelta(days=2)), 22.5)

    def test_cross_month_boundary(self):
        self.assertEqual(calculate_available_hours(40, date(2026, 10, 30), date(2026, 11, 2)), 16)

    def test_cross_year_boundary(self):
        self.assertEqual(calculate_available_hours(40, date(2026, 12, 31), date(2027, 1, 4)), 24)


class TestDeadlineGroups(unittest.TestCase):
    def test_empty_tasks(self):
        groups = group_tasks_by_deadline([], TODAY)
        self.assertEqual(groups, {'overdue': [], 'within_1_week': [], 'week_2': [], 'after_2_weeks': []})

    def test_overdue_boundary(self):
        task = make_task(2, -1)
        self.assertEqual(group_tasks_by_deadline([task], TODAY)['overdue'], [task])

    def test_due_today(self):
        task = make_task(2, 0)
        self.assertEqual(group_tasks_by_deadline([task], TODAY)['within_1_week'], [task])

    def test_day_seven(self):
        task = make_task(2, 7)
        self.assertEqual(group_tasks_by_deadline([task], TODAY)['within_1_week'], [task])

    def test_day_eight(self):
        task = make_task(2, 8)
        self.assertEqual(group_tasks_by_deadline([task], TODAY)['week_2'], [task])

    def test_day_fourteen(self):
        task = make_task(2, 14)
        self.assertEqual(group_tasks_by_deadline([task], TODAY)['week_2'], [task])

    def test_day_fifteen(self):
        task = make_task(2, 15)
        self.assertEqual(group_tasks_by_deadline([task], TODAY)['after_2_weeks'], [task])

    def test_completed_tasks_are_excluded(self):
        groups = group_tasks_by_deadline([make_task(3, 2, 'Completed')], TODAY)
        self.assertTrue(all(not group for group in groups.values()))

    def test_completed_overdue_task_excluded(self):
        task = make_task(8, -5, "Completed")
        groups = group_tasks_by_deadline([task], TODAY)
        self.assertEqual(groups["overdue"], [])

    def test_each_active_task_appears_once(self):
        tasks = [make_task(1, d) for d in (-1, 0, 7, 8, 14, 15)]
        groups = group_tasks_by_deadline(tasks, TODAY)
        self.assertEqual([len(groups[key]) for key in ('overdue', 'within_1_week', 'week_2', 'after_2_weeks')], [1, 2, 2, 1])
        self.assertEqual(sum(map(len, groups.values())), len(tasks))

    def test_invalid_active_deadline_raises(self):
        task = make_task(2, 1)
        task['deadline'] = '2026-02-30'
        with self.assertRaises(ValueError):
            group_tasks_by_deadline([task], TODAY)


class TestHoursDueBy(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(calculate_hours_due_by([], TODAY), 0)

    def test_before_and_on_cutoff_included(self):
        tasks = [make_task(3, -1), make_task(4, 0), make_task(5, 1)]
        self.assertEqual(calculate_hours_due_by(tasks, TODAY), 7)

    def test_later_tasks_excluded(self):
        self.assertEqual(calculate_hours_due_by([make_task(5, 3)], TODAY), 0)

    def test_completed_tasks_excluded(self):
        tasks = [make_task(5, -1, 'Completed'), make_task(2, 0)]
        self.assertEqual(calculate_hours_due_by(tasks, TODAY), 2)

    def test_fractional_hours(self):
        tasks = [make_task(1.25, 0), make_task(2.5, -1)]
        self.assertAlmostEqual(calculate_hours_due_by(tasks, TODAY), 3.75)

    def test_cumulative_hours_across_deadlines(self):
        tasks = [make_task(10, 2), make_task(15, 5), make_task(20, 12)]
        self.assertEqual(calculate_hours_due_by(tasks, TODAY + timedelta(days=5)), 25)
        self.assertEqual(calculate_hours_due_by(tasks, TODAY + timedelta(days=12)), 45)

    def test_invalid_active_deadline_raises(self):
        task = make_task(2, 1)
        task['deadline'] = 'not-a-date'
        with self.assertRaises(ValueError):
            calculate_hours_due_by([task], TODAY)


class TestDeadlineConflicts(unittest.TestCase):
    def setUp(self):
        # James works 30 hours per week (6 per weekday).
        self.employee = {"employee_id": 2, "name": "James", "available_hours": 30}

    def test_no_tasks(self):
        conflicts = check_deadline_conflicts(self.employee, [], TODAY)
        self.assertEqual(conflicts, [])

    def test_task_within_available_capacity(self):
        # Monday through Thursday = 24 available hours.
        task = make_task(15, 3)
        conflicts = check_deadline_conflicts(self.employee, [task], TODAY)
        self.assertEqual(conflicts, [])

    def test_task_exceeds_available_capacity(self):
        task = make_task(30, 3)
        conflicts = check_deadline_conflicts(self.employee, [task], TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "capacity")
        self.assertEqual(conflicts[0]["required_hours"], 30)
        self.assertEqual(conflicts[0]["available_hours"], 24)
        self.assertEqual(conflicts[0]["shortfall_hours"], 6)

    def test_exactly_enough_capacity(self):
        task = make_task(24, 3)
        conflicts = check_deadline_conflicts(self.employee, [task], TODAY)
        self.assertEqual(conflicts, [])

    def test_combined_tasks_exceed_capacity(self):
        tasks = [make_task(15, 3),make_task(15, 3)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["required_hours"], 30)
        self.assertEqual(conflicts[0]["shortfall_hours"], 6)

    def test_earlier_deadline_counts_toward_later_deadline(self):
        tasks = [make_task(22, 3),make_task(30, 9)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["deadline"], (TODAY + timedelta(days=9)).isoformat())
        self.assertEqual(conflicts[0]["required_hours"], 52)
        self.assertEqual(conflicts[0]["available_hours"], 48)
        self.assertEqual(conflicts[0]["shortfall_hours"], 4)

    def test_later_deadline_does_not_affect_earlier_deadline(self):
        tasks = [make_task(30, 3), make_task(8, 9)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["required_hours"], 30)
        self.assertEqual(conflicts[0]["deadline"], (TODAY + timedelta(days=3)).isoformat())

    def test_multiple_conflicting_deadlines(self):
        tasks = [make_task(30, 3), make_task(30, 9)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(len(conflicts), 2)
        self.assertEqual([conflict["required_hours"] for conflict in conflicts], [30, 60])
        self.assertTrue(all(conflict["type"] == "capacity" for conflict in conflicts))

    def test_completed_tasks_are_excluded(self):
        tasks = [make_task(15, 3), make_task(50, 3, "Completed")]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(conflicts, [])

    def test_completed_overdue_tasks_are_excluded(self):
        task = make_task(10, -2, "Completed")
        conflicts = check_deadline_conflicts(self.employee, [task], TODAY)
        self.assertEqual(conflicts, [])

    def test_overdue_task_is_reported(self):
        task = make_task(8, -1)
        conflicts = check_deadline_conflicts(self.employee, [task], TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "overdue")
        self.assertEqual(conflicts[0]["required_hours"], 8)
        self.assertEqual(conflicts[0]["available_hours"], 0)
        self.assertEqual(conflicts[0]["shortfall_hours"], 8)

    def test_multiple_overdue_tasks(self):
        tasks = [make_task(5, -3), make_task(7, -1)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(len(conflicts), 2)
        self.assertTrue(all(conflict["type"] == "overdue" for conflict in conflicts))

    def test_overdue_and_upcoming_conflicts(self):
        tasks = [make_task(8, -1), make_task(30, 3)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(len(conflicts), 3)
        self.assertEqual(
            [conflict["type"] for conflict in conflicts],
            ["overdue", "capacity", "capacity"]
        )
        self.assertEqual(conflicts[1]["required_hours"], 30)
        self.assertEqual(conflicts[1]["available_hours"], 24)
        self.assertEqual(conflicts[1]["shortfall_hours"], 6)
        self.assertEqual(conflicts[2]["deadline"], (TODAY + timedelta(days=4)).isoformat())
        self.assertEqual(conflicts[2]["required_hours"], 38)
        self.assertEqual(conflicts[2]["available_hours"], 30)
        self.assertEqual(conflicts[2]["shortfall_hours"], 8)

    def test_overdue_hours_count_toward_future_capacity(self):
        tasks = [make_task(20, -1), make_task(15, 3)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(len(conflicts), 2)
        self.assertEqual(conflicts[0]["type"], "overdue")
        self.assertEqual(conflicts[1]["type"], "capacity")
        self.assertEqual(
            conflicts[1]["deadline"],
            (TODAY + timedelta(days=4)).isoformat()
        )
        self.assertEqual(conflicts[1]["required_hours"], 35)
        self.assertEqual(conflicts[1]["available_hours"], 30)
        self.assertEqual(conflicts[1]["shortfall_hours"], 5)

    def test_completed_overdue_hours_do_not_count_toward_capacity(self):
        tasks = [make_task(20, -1, "Completed"), make_task(15, 3)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(conflicts, [])

    def test_deadline_today(self):
        task = make_task(8, 0)
        conflicts = check_deadline_conflicts(self.employee, [task], TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["available_hours"], 6)
        self.assertEqual(conflicts[0]["shortfall_hours"], 2)

    def test_weekend_deadline(self):
        task = make_task(35, 5)
        conflicts = check_deadline_conflicts(self.employee, [task], TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["available_hours"], 30)
        self.assertEqual(conflicts[0]["shortfall_hours"], 5)

    def test_zero_available_hours(self):
        employee = {"employee_id": 3, "name": "Alex", "available_hours": 0}
        task = make_task(5, 3)
        conflicts = check_deadline_conflicts(employee, [task], TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["available_hours"], 0)
        self.assertEqual(conflicts[0]["shortfall_hours"], 5)

    def test_fractional_hours(self):
        task = make_task(24.5, 3)
        conflicts = check_deadline_conflicts(self.employee, [task], TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertAlmostEqual(conflicts[0]["shortfall_hours"], 0.5)

    def test_tasks_can_span_multiple_weeks(self):
        task = make_task(70, 15)
        conflicts = check_deadline_conflicts(self.employee, [task], TODAY)
        self.assertEqual(conflicts, [])

    def test_deadlines_are_checked_chronologically(self):
        tasks = [make_task(40, 9), make_task(30, 3)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(len(conflicts), 2)
        self.assertEqual(conflicts[0]["deadline"], (TODAY + timedelta(days=3)).isoformat())
        self.assertEqual(conflicts[1]["deadline"], (TODAY + timedelta(days=9)).isoformat())

    def test_no_duplicate_capacity_conflicts_for_same_deadline(self):
        tasks = [make_task(20, 3), make_task(15, 3), make_task(10, 3)]
        conflicts = check_deadline_conflicts(self.employee, tasks, TODAY)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["required_hours"], 45)
        self.assertEqual(conflicts[0]["shortfall_hours"], 21)


class TestCalculateUtilization(unittest.TestCase):
    def setUp(self):self.employee = {"employee_id": 1, "name": "Sarah", "available_hours": 40}

    def test_no_tasks(self):
        result = calculate_utilization(self.employee, [], TODAY)
        self.assertEqual(result["one_week"], 0.0)
        self.assertEqual(result["two_weeks"], 0.0)

    def test_one_task_due_within_first_week(self):
        tasks = [make_task(24, 3)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["one_week"], 50.0)
        self.assertAlmostEqual(result["two_weeks"], (24 / 88) * 100)

    def test_task_due_in_second_week(self):
        tasks = [make_task(22, 10)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertEqual(result["one_week"], 0.0)
        self.assertAlmostEqual(result["two_weeks"], 25.0)

    def test_two_weeks_includes_first_week(self):
        tasks = [make_task(24, 3), make_task(20, 10)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["one_week"], 50.0)
        self.assertAlmostEqual(result["two_weeks"], 50.0)

    def test_tasks_after_two_weeks_excluded(self):
        tasks = [make_task(30, 21)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertEqual(result["one_week"], 0.0)
        self.assertEqual(result["two_weeks"], 0.0)

    def test_overdue_tasks_included(self):
        tasks = [make_task(12, -2)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["one_week"], 25.0)
        self.assertAlmostEqual(result["two_weeks"], (12 / 88) * 100)

    def test_completed_tasks_excluded(self):
        tasks = [make_task(24, 3, "Completed"), make_task(12, 10)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertEqual(result["one_week"], 0.0)
        self.assertAlmostEqual(result["two_weeks"], (12 / 88) * 100)

    def test_task_due_today(self):
        tasks = [make_task(8, 0)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["one_week"], (8 / 48) * 100)
        self.assertAlmostEqual(result["two_weeks"], (8 / 88) * 100)

    def test_task_due_on_day_seven(self):
        tasks = [make_task(24, 7)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["one_week"], 50.0)
        self.assertAlmostEqual(result["two_weeks"], (24 / 88) * 100)

    def test_task_due_on_day_fourteen(self):
        tasks = [make_task(44, 14)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertEqual(result["one_week"], 0.0)
        self.assertAlmostEqual(result["two_weeks"], 50.0)

    def test_task_due_on_day_fifteen_excluded(self):
        tasks = [make_task(44, 15)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertEqual(result["one_week"], 0.0)
        self.assertEqual(result["two_weeks"], 0.0)

    def test_over_capacity(self):
        tasks = [make_task(60, 3)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["one_week"], 125.0)
        self.assertAlmostEqual(result["two_weeks"], (60 / 88) * 100)

    def test_fractional_hours(self):
        tasks = [make_task(7.5, 3)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["one_week"], (7.5 / 48) * 100)
        self.assertAlmostEqual(result["two_weeks"], (7.5 / 88) * 100)

    def test_zero_weekly_availability(self):
        employee = {"employee_id": 2, "name": "Alex", "available_hours": 0}
        tasks = [make_task(10, 3)]
        result = calculate_utilization(employee, tasks, TODAY)
        self.assertIsNone(result["one_week"])
        self.assertIsNone(result["two_weeks"])

    def test_zero_availability_and_no_tasks(self):
        employee = {"employee_id": 2,"name": "Alex","available_hours": 0}
        result = calculate_utilization(employee, [], TODAY)
        self.assertIsNone(result["one_week"])
        self.assertIsNone(result["two_weeks"])

    def test_negative_weekly_availability(self):
        employee = {"employee_id": 2, "name": "Alex","available_hours": -5}
        with self.assertRaises(ValueError):
            calculate_utilization(employee, [], TODAY)

    def test_multiple_tasks_same_deadline(self):
        tasks = [make_task(10, 3), make_task(14, 3), make_task(20, 10)]
        result = calculate_utilization(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["one_week"], 50.0)
        self.assertAlmostEqual(result["two_weeks"], 50.0)


class TestEmployeeWorkloadSummary(unittest.TestCase):
    def setUp(self):
        self.employee = {"employee_id": 1, "name": "Sarah", "experience_level": "Senior","available_hours": 40}

    def test_empty_workload(self):
        result = get_employee_workload_summary(self.employee, [], TODAY)
        self.assertEqual(result["outstanding_hours"], 0)
        self.assertEqual(result["active_task_count"], 0)
        self.assertEqual(result["overdue_task_count"], 0)
        self.assertEqual(result["one_week_utilization"], 0.0)
        self.assertEqual(result["two_week_utilization"], 0.0)
        self.assertEqual(result["deadline_conflicts"], [])

    def test_employee_information(self):
        result = get_employee_workload_summary(self.employee, [], TODAY)
        self.assertEqual(result["employee_id"], 1)
        self.assertEqual(result["name"], "Sarah")
        self.assertEqual(result["experience_level"], "Senior")
        self.assertEqual(result["available_hours"], 40)

    def test_outstanding_hours(self):
        tasks = [make_task(10, 3), make_task(20, 10), make_task(15, 5, "Completed")]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["outstanding_hours"], 30)

    def test_fractional_outstanding_hours(self):
        tasks = [make_task(2.5, 3), make_task(7.75, 10)]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["outstanding_hours"], 10.25)

    def test_active_task_count(self):
        tasks = [make_task(10, 3), make_task(20, 10), make_task(15, 5, "Completed")]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["active_task_count"], 2)

    def test_deadline_group_counts(self):
        tasks = [
            make_task(5, -2),
            make_task(10, 3),
            make_task(15, 10),
            make_task(20, 21),
            make_task(8, 3, "Completed")
        ]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["overdue_task_count"], 1)
        self.assertEqual(result["within_1_week_count"], 1)
        self.assertEqual(result["week_2_count"], 1)
        self.assertEqual(result["after_2_weeks_count"], 1)

    def test_utilization_values(self):
        tasks = [make_task(24, 3),make_task(20, 10)]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertAlmostEqual(result["one_week_utilization"], 50.0)
        self.assertAlmostEqual(result["two_week_utilization"], 50.0)

    def test_deadline_conflicts_included(self):
        tasks = [make_task(60, 3)]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(len(result["deadline_conflicts"]), 1)
        self.assertEqual(result["deadline_conflicts"][0]["type"], "capacity")

    def test_multiple_deadline_conflicts(self):
        tasks = [make_task(40, 3), make_task(40, 10)]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(len(result["deadline_conflicts"]), 2)

    def test_no_deadline_conflicts(self):
        tasks = [make_task(8, 3)]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["deadline_conflicts"], [])

    def test_deadline_group_boundaries(self):
        tasks = [make_task(5, 7), make_task(10, 8), make_task(15, 14), make_task(20, 15)]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["within_1_week_count"], 1)
        self.assertEqual(result["week_2_count"], 2)
        self.assertEqual(result["after_2_weeks_count"], 1)

    def test_completed_tasks_excluded(self):
        tasks = [make_task(10, 3, "Completed"), make_task(15, -2, "Completed")]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["outstanding_hours"], 0)
        self.assertEqual(result["active_task_count"], 0)
        self.assertEqual(result["overdue_task_count"], 0)
        self.assertEqual(result["deadline_conflicts"], [])

    def test_zero_availability(self):
        employee = {"employee_id": 2, "name": "Alex", "experience_level": "Junior", "available_hours": 0}
        tasks = [make_task(10, 3, employee_id=2)]
        result = get_employee_workload_summary(employee, tasks, TODAY)
        self.assertEqual(result["outstanding_hours"], 10)
        self.assertIsNone(result["one_week_utilization"])
        self.assertIsNone(result["two_week_utilization"])
        self.assertEqual(len(result["deadline_conflicts"]), 1)

    def test_overdue_task_conflict(self):
        tasks = [make_task(10, -2)]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["overdue_task_count"], 1)
        self.assertEqual(result["deadline_conflicts"][0]["type"], "overdue")

    def test_multiple_overdue_tasks(self):
        tasks = [make_task(5, -3), make_task(10, -1), make_task(8, 3)]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["overdue_task_count"], 2)
        self.assertEqual(result["active_task_count"], 3)
        self.assertEqual(result["outstanding_hours"], 23)
        self.assertEqual(len(result["deadline_conflicts"]), 2)

    def test_tasks_after_two_weeks(self):
        tasks = [make_task(20, 21)]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["outstanding_hours"], 20)
        self.assertEqual(result["after_2_weeks_count"], 1)
        self.assertEqual(result["one_week_utilization"], 0.0)
        self.assertEqual(result["two_week_utilization"], 0.0)

    def test_excludes_other_employees_tasks(self):
        tasks = [
            make_task(10, 3, employee_id=1),
            make_task(20, 3, employee_id=2),
            make_task(15, 10, employee_id=1),
            make_task(8, 3, employee_id=None)
        ]
        result = get_employee_workload_summary(self.employee, tasks, TODAY)
        self.assertEqual(result["outstanding_hours"], 25)
        self.assertEqual(result["active_task_count"], 2)
        self.assertAlmostEqual(result["one_week_utilization"],(10 / 48) * 100)
        self.assertAlmostEqual(result["two_week_utilization"],(25 / 88) * 100)
        self.assertEqual(result["deadline_conflicts"], [])

class TestUpcomingDeadlines(unittest.TestCase):
    def test_empty_tasks(self):
        result = get_upcoming_deadlines([], TODAY)
        self.assertEqual(result, [])

    def test_tasks_sorted_by_deadline(self):
        tasks = [make_task(10, 10), make_task(5, 2), make_task(8, 6)]
        result = get_upcoming_deadlines(tasks, TODAY)
        self.assertEqual([task["estimated_hours"] for task in result], [5, 8, 10])

    def test_overdue_tasks_included(self):
        tasks = [make_task(10, 5), make_task(8, -3), make_task(6, 0)]
        result = get_upcoming_deadlines(tasks, TODAY)
        self.assertEqual([task["estimated_hours"] for task in result], [8, 6, 10])

    def test_completed_tasks_excluded(self):
        tasks = [make_task(10, 3), make_task(5, 1, status="Completed"), make_task(8, 6)]
        result = get_upcoming_deadlines(tasks, TODAY)
        self.assertEqual(len(result), 2)
        self.assertEqual([task["estimated_hours"] for task in result], [10, 8])

    def test_unassigned_tasks_included(self):
        tasks = [make_task(10, 3, employee_id=None), make_task(5, 5, employee_id=1)]
        result = get_upcoming_deadlines(tasks, TODAY)
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0]["employee_id"])

    def test_same_deadline_preserves_order(self):
        tasks = [make_task(10, 3), make_task(5, 3), make_task(8, 3)]
        result = get_upcoming_deadlines(tasks, TODAY)
        self.assertEqual([task["estimated_hours"] for task in result],[10, 5, 8])

    def test_original_list_not_modified(self):
        tasks = [make_task(10, 10), make_task(5, 2)]
        original_order = tasks.copy()
        get_upcoming_deadlines(tasks, TODAY)
        self.assertEqual(tasks, original_order)


class TestTeamWorkloadSummary(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {
                "employee_id": 1,
                "name": "Sarah",
                "experience_level": "Senior",
                "available_hours": 40
            },
            {
                "employee_id": 2,
                "name": "James",
                "experience_level": "Mid",
                "available_hours": 40
            },
            {
                "employee_id": 3,
                "name": "Alex",
                "experience_level": "Junior",
                "available_hours": 20
            }
        ]

    def make_task(self, hours, days, employee_id=1, status="Active", priority="Low", difficulty="Easy"):
        return {
            "estimated_hours": hours,
            "deadline": (TODAY + timedelta(days=days)).isoformat(),
            "employee_id": employee_id,
            "status": status,
            "priority": priority,
            "difficulty": difficulty
        }

    def test_empty_team(self):
        result = get_team_workload_summary([], [], TODAY)
        self.assertEqual(result["total_employees"], 0)
        self.assertEqual(result["active_tasks"], 0)
        self.assertEqual(result["unassigned_tasks"], 0)
        self.assertEqual(result["outstanding_hours"], 0)
        self.assertEqual(result["overdue_tasks"], 0)
        self.assertEqual(result["employees"], [])
        self.assertEqual(result["upcoming_deadlines"], [])
        self.assertIsNone(result["fairness"]["one_week_utilization_spread"])

    def test_employees_without_tasks(self):
        result = get_team_workload_summary(self.employees, [], TODAY)
        self.assertEqual(result["total_employees"], 3)
        self.assertEqual(result["active_tasks"], 0)
        self.assertEqual(result["outstanding_hours"], 0)
        self.assertEqual(len(result["employees"]), 3)
        self.assertEqual(
            [s["active_task_count"] for s in result["employees"]],
            [0, 0, 0]
        )

    def test_tasks_distributed_across_employees(self):
        tasks = [
            self.make_task(10, 3, employee_id=1),
            self.make_task(5, 5, employee_id=1),
            self.make_task(8, 10, employee_id=2),
            self.make_task(6, 12, employee_id=3)
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(result["active_tasks"], 4)
        self.assertEqual(result["outstanding_hours"], 29)
        summaries = {
            s["employee_id"]: s
            for s in result["employees"]
        }
        self.assertEqual(summaries[1]["outstanding_hours"], 15)
        self.assertEqual(summaries[2]["outstanding_hours"], 8)
        self.assertEqual(summaries[3]["outstanding_hours"], 6)

    def test_unassigned_tasks_counted_separately(self):
        tasks = [
            self.make_task(10, 3, employee_id=1),
            self.make_task(8, 5, employee_id=None),
            self.make_task(6, 7, employee_id=None)
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(result["active_tasks"], 1)
        self.assertEqual(result["unassigned_tasks"], 2)
        self.assertEqual(result["outstanding_hours"], 10)
        self.assertEqual(len(result["upcoming_deadlines"]), 3)

    def test_completed_tasks_excluded(self):
        tasks = [
            self.make_task(10, 3, employee_id=1),
            self.make_task(20, -5, employee_id=2, status="Completed"),
            self.make_task(8, 5, employee_id=None, status="Completed")
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(result["active_tasks"], 1)
        self.assertEqual(result["unassigned_tasks"], 0)
        self.assertEqual(result["outstanding_hours"], 10)
        self.assertEqual(result["overdue_tasks"], 0)
        self.assertEqual(len(result["upcoming_deadlines"]), 1)

    def test_overdue_tasks(self):
        tasks = [
            self.make_task(10, -3, employee_id=1),
            self.make_task(5, -1, employee_id=2),
            self.make_task(8, 3, employee_id=3)
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(result["overdue_tasks"], 2)

    def test_multiple_conflicts_same_employee(self):
        tasks = [
            self.make_task(10, -3, employee_id=1),
            self.make_task(5, -1, employee_id=1)
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(result["employees_with_conflicts"], 1)
        self.assertEqual(result["total_deadline_conflicts"], 2)

    def test_conflicts_across_multiple_employees(self):
        tasks = [
            self.make_task(10, -3, employee_id=1),
            self.make_task(5, -1, employee_id=2)
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(result["employees_with_conflicts"], 2)
        self.assertEqual(result["total_deadline_conflicts"], 2)

    def test_no_conflicts(self):
        tasks = [
            self.make_task(5, 3, employee_id=1),
            self.make_task(8, 10, employee_id=2)
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(result["employees_with_conflicts"], 0)
        self.assertEqual(result["total_deadline_conflicts"], 0)

    def test_fairness_included(self):
        tasks = [
            self.make_task(10, 3, employee_id=1, priority="High", difficulty="Hard"),
            self.make_task(5, 5, employee_id=1, priority="High", difficulty="Easy"),
            self.make_task(8, 10, employee_id=2, priority="Low", difficulty="Hard")
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        fairness = result["fairness"]
        self.assertEqual(
            fairness["high_priority_tasks"][1],
            {"count": 2, "hours": 15}
        )
        self.assertEqual(
            fairness["difficult_tasks"][1],
            {"count": 1, "hours": 10}
        )
        self.assertEqual(
            fairness["difficult_tasks"][2],
            {"count": 1, "hours": 8}
        )
        self.assertIsNotNone(fairness["one_week_utilization_spread"])

    def test_upcoming_deadlines_sorted(self):
        tasks = [
            self.make_task(10, 10),
            self.make_task(5, -2),
            self.make_task(8, 3, employee_id=None)
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(
            [t["estimated_hours"]
             for t in result["upcoming_deadlines"]],
            [5, 8, 10]
        )

    def test_unknown_employee_excluded_from_totals(self):
        tasks = [
            self.make_task(10, 3, employee_id=1),
            self.make_task(20, 5, employee_id=99)
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(result["active_tasks"], 1)
        self.assertEqual(result["outstanding_hours"], 10)

    def test_zero_availability_employee(self):
        employees = [
            {
                "employee_id": 1,
                "name": "Sarah",
                "experience_level": "Senior",
                "available_hours": 0
            },
            self.employees[1]
        ]
        tasks = [self.make_task(10, 3, employee_id=1)]
        result = get_team_workload_summary(employees, tasks, TODAY)
        summaries = {
            s["employee_id"]: s
            for s in result["employees"]
        }
        self.assertIsNone(
            summaries[1]["one_week_utilization"]
        )
        self.assertEqual(
            result["employees_with_conflicts"], 1
        )

    def test_fractional_hours(self):
        tasks = [
            self.make_task(2.5, 3, employee_id=1),
            self.make_task(7.75, 10, employee_id=2)
        ]
        result = get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertAlmostEqual(result["outstanding_hours"], 10.25)

    def test_original_inputs_not_modified(self):
        tasks = [
            self.make_task(10, 3, employee_id=1),
            self.make_task(5, 10, employee_id=2)
        ]
        original_employees = [employee.copy() for employee in self.employees]
        original_tasks = [task.copy() for task in tasks]
        get_team_workload_summary(self.employees, tasks, TODAY)
        self.assertEqual(self.employees, original_employees)
        self.assertEqual(tasks, original_tasks)

if __name__ == '__main__':
    unittest.main()
