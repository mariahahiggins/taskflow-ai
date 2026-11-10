import unittest

from datetime import date

from unittest.mock import patch

from backend.assignment import (
    find_assignment_records,
    validate_assignment_records,
    validate_experience,
    validate_deadline_capacity,
    compare_fairness,
    validate_fairness,
    find_duplicate_task_ids,
    simulate_recommendations,
    validate_recommendations,
    evaluate_selected_changes,
    evaluate_individual_recommendation
)

class TestAssignmentRecords(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {"employee_id": 1, "name": "Alex"},
            {"employee_id": 2, "name": "Taylor"},
        ]
        self.tasks = [
            {"task_id": 101, "title": "Documentation"},
            {"task_id": 102, "title": "API Integration"},
        ]

    def test_valid_employee_and_task(self):
        employee, task = find_assignment_records(
            self.employees, self.tasks, 101, 2
        )
        self.assertEqual(employee["name"], "Taylor")
        self.assertEqual(task["title"], "Documentation")

    def test_invalid_employee(self):
        employee, task = find_assignment_records(
            self.employees, self.tasks, 101, 999
        )
        self.assertIsNone(employee)
        self.assertIsNotNone(task)

    def test_invalid_task(self):
        employee, task = find_assignment_records(
            self.employees, self.tasks, 999, 1
        )
        self.assertIsNotNone(employee)
        self.assertIsNone(task)

class TestAssignmentValidation(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {"employee_id": 1, "name": "Alex"},
        ]
        self.tasks = [
            {"task_id": 101, "status": "Active"},
            {"task_id": 102, "status": "Completed"},
        ]

    def test_active_task_is_valid(self):
        errors = validate_assignment_records(
            self.employees, self.tasks, 101, 1
        )
        self.assertEqual(errors, [])

    def test_completed_task_is_rejected(self):
        errors = validate_assignment_records(
            self.employees, self.tasks, 102, 1
        )
        self.assertIn("Task is already completed.", errors)

    def test_missing_employee_is_rejected(self):
        errors = validate_assignment_records(
            self.employees, self.tasks, 101, 999
        )
        self.assertIn("Employee does not exist.", errors)

    def test_missing_task_is_rejected(self):
        errors = validate_assignment_records(
            self.employees, self.tasks, 999, 1
        )
        self.assertIn("Task does not exist.", errors)

    def test_both_records_missing(self):
        errors = validate_assignment_records(
            self.employees, self.tasks, 999, 999
        )
        self.assertEqual(len(errors), 2)

class TestExperienceValidation(unittest.TestCase):
    def test_junior_easy_allowed(self):
        employee = {"experience_level": "Junior"}
        task = {"difficulty": "Easy"}
        errors, warnings = validate_experience(employee, task)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_junior_medium_warning(self):
        employee = {"experience_level": "Junior"}
        task = {"difficulty": "Medium"}
        errors, warnings = validate_experience(employee, task)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)

    def test_junior_hard_rejected(self):
        employee = {"experience_level": "Junior"}
        task = {"difficulty": "Hard"}
        errors, warnings = validate_experience(employee, task)
        self.assertEqual(len(errors), 1)
        self.assertEqual(warnings, [])

    def test_mid_easy_allowed(self):
        employee = {"experience_level": "Mid"}
        task = {"difficulty": "Easy"}
        errors, warnings = validate_experience(employee, task)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_mid_medium_allowed(self):
        employee = {"experience_level": "Mid"}
        task = {"difficulty": "Medium"}
        errors, warnings = validate_experience(employee, task)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_mid_hard_warning(self):
        employee = {"experience_level": "Mid"}
        task = {"difficulty": "Hard"}
        errors, warnings = validate_experience(employee, task)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)

    def test_senior_hard_allowed(self):
        employee = {"experience_level": "Senior"}
        task = {"difficulty": "Hard"}
        errors, warnings = validate_experience(employee, task)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class TestDeadlineCapacityValidation(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 9)  # Monday
        self.employees = [
            {
                "employee_id": 1,
                "name": "Alex",
                "available_hours": 40,
                "experience_level": "Senior"
            },
            {
                "employee_id": 2,
                "name": "Taylor",
                "available_hours": 40,
                "experience_level": "Senior"
            }
        ]

    def make_task(self, task_id, hours, deadline, employee_id=None):
        return {
            "task_id": task_id,
            "estimated_hours": hours,
            "deadline": deadline,
            "employee_id": employee_id,
            "status": "Active"
        }

    def check_capacity(self, tasks, recommendations):
        proposed_tasks = simulate_recommendations(tasks, recommendations)
        return validate_deadline_capacity(self.employees, tasks, proposed_tasks, self.today)

    def test_single_assignment_within_capacity(self):
        tasks = [self.make_task(101, 20, "2026-11-13")]
        errors = self.check_capacity(tasks, [{"task_id": 101, "employee_id": 1}])
        self.assertEqual(errors, {})

    def test_single_assignment_exceeds_capacity(self):
        tasks = [self.make_task(101, 30, "2026-11-13", 1), self.make_task(102, 15, "2026-11-13")]
        errors = self.check_capacity(tasks, [{"task_id": 102, "employee_id": 1}])
        self.assertIn(1, errors)
        self.assertIn(
            "Proposed assignments worsen capacity by 5.0 hours "
            "for deadline 2026-11-13.",
            errors[1]
        )

    def test_multiple_assignments_exceed_capacity(self):
        tasks = [self.make_task(101, 25, "2026-11-13"), self.make_task(102, 20, "2026-11-13")]
        recommendations = [{"task_id": 101, "employee_id": 1}, {"task_id": 102, "employee_id": 1}]
        errors = self.check_capacity(tasks, recommendations)
        self.assertIn(1, errors)

    def test_multiple_assignments_fit_capacity(self):
        tasks = [self.make_task(101, 15, "2026-11-13"), self.make_task(102, 20, "2026-11-13")]
        recommendations = [{"task_id": 101, "employee_id": 1}, {"task_id": 102, "employee_id": 1}]
        errors = self.check_capacity(tasks, recommendations)
        self.assertEqual(errors, {})

    def test_task_can_span_multiple_weeks(self):
        tasks = [self.make_task(101, 60, "2026-11-20")]
        errors = self.check_capacity(tasks, [{"task_id": 101, "employee_id": 1}])
        self.assertEqual(errors, {})

    def test_different_deadlines(self):
        tasks = [self.make_task(101, 35, "2026-11-13"), self.make_task(102, 35, "2026-11-20")]
        recommendations = [{"task_id": 101, "employee_id": 1},{"task_id": 102, "employee_id": 1}]
        errors = self.check_capacity(tasks, recommendations)
        self.assertEqual(errors, {})

    def test_earlier_deadline_exceeds_capacity(self):
        tasks = [self.make_task(101, 45, "2026-11-13"), self.make_task(102, 10, "2026-11-20")]
        recommendations = [{"task_id": 101, "employee_id": 1},{"task_id": 102, "employee_id": 1}]
        errors = self.check_capacity(tasks, recommendations)
        self.assertIn(1, errors)
        self.assertTrue(
            any("2026-11-13" in error for error in errors[1])
        )

    def test_existing_conflict_not_worsened(self):
        tasks = [self.make_task(101, 45, "2026-11-13", 1), self.make_task(102, 5, "2026-11-27")]
        errors = self.check_capacity(tasks, [{"task_id": 102, "employee_id": 1}])
        self.assertEqual(errors, {})

    def test_existing_conflict_worsened(self):
        tasks = [self.make_task(101, 45, "2026-11-13", 1), self.make_task(102, 10, "2026-11-13")]
        errors = self.check_capacity(tasks, [{"task_id": 102, "employee_id": 1}])
        self.assertIn(1, errors)

    def test_reassignment_within_capacity(self):
        tasks = [self.make_task(101, 10, "2026-11-13", 2), self.make_task(102, 20, "2026-11-13", 1)]
        errors = self.check_capacity(tasks, [{"task_id": 101, "employee_id": 1}])
        self.assertEqual(errors, {})

    def test_reassignment_reduces_workload(self):
        tasks = [self.make_task(101, 30, "2026-11-13", 1), self.make_task(102, 20, "2026-11-13", 1)]
        errors = self.check_capacity(tasks, [{"task_id": 102, "employee_id": 2}])
        self.assertEqual(errors, {})

    def test_original_tasks_not_modified(self):
        tasks = [self.make_task(101, 10, "2026-11-13")]
        self.check_capacity(tasks, [{"task_id": 101, "employee_id": 1}])
        self.assertIsNone(tasks[0]["employee_id"])

    def test_completed_tasks_excluded(self):
        tasks = [
            self.make_task(101, 35, "2026-11-13", 1),
            self.make_task(102, 20, "2026-11-13", 1),
            self.make_task(103, 5, "2026-11-13")
        ]
        tasks[1]["status"] = "Completed"
        errors = self.check_capacity(tasks, [{"task_id": 103, "employee_id": 1}])
        self.assertEqual(errors, {})

    def test_no_recommendations(self):
        tasks = [self.make_task(101, 45, "2026-11-13", 1)]
        errors = self.check_capacity(tasks, [])
        self.assertEqual(errors, {})

    def test_overdue_reassignment_reduces_conflict(self):
        tasks = [self.make_task(101, 10, "2026-11-06", 1), self.make_task(102, 35, "2026-11-13", 1),]
        errors = self.check_capacity(tasks, [{"task_id": 101, "employee_id": 2}])
        self.assertEqual(errors, {})

class TestFairnessComparison(unittest.TestCase):
    def setUp(self):
        self.before = {
            "one_week_utilization_spread": 0.2,
            "two_week_utilization_spread": 0.1,
            "high_priority_count_spread": 1,
            "high_priority_hours_spread": 5,
            "difficult_count_spread": 0,
            "difficult_hours_spread": 0
        }

    def test_no_fairness_change(self):
        after = self.before.copy()
        warnings = compare_fairness(self.before, after)
        self.assertEqual(warnings, [])

    def test_high_priority_imbalance_increases(self):
        after = self.before.copy()
        after["high_priority_count_spread"] = 2
        warnings = compare_fairness(self.before, after)
        self.assertIn("High-priority task distribution becomes less balanced.", warnings)

    def test_utilization_imbalance_increases(self):
        after = self.before.copy()
        after["one_week_utilization_spread"] = 0.4
        warnings = compare_fairness(self.before, after)
        self.assertIn("One-week workload balance becomes less balanced.", warnings)

    def test_improved_fairness_no_warning(self):
        after = self.before.copy()
        after["high_priority_count_spread"] = 0
        warnings = compare_fairness(self.before, after)
        self.assertEqual(warnings, [])

    def test_none_metrics_skipped(self):
        after = self.before.copy()
        after["one_week_utilization_spread"] = None
        warnings = compare_fairness(self.before, after)
        self.assertEqual(warnings, [])

    def test_multiple_fairness_warnings(self):
        after = self.before.copy()
        after["high_priority_count_spread"] = 2
        after["difficult_hours_spread"] = 10
        warnings = compare_fairness(self.before, after)
        self.assertEqual(len(warnings), 2)

class TestFairnessValidation(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 9)
        self.employees = [{"employee_id": 1}, {"employee_id": 2}]
        self.tasks = [{"task_id": 101, "employee_id": None}]
        self.proposed_tasks = [{"task_id": 101, "employee_id": 1}]
        self.before_fairness = {
            "one_week_utilization_spread": 0.1,
            "two_week_utilization_spread": 0.1,
            "high_priority_count_spread": 0,
            "high_priority_hours_spread": 0,
            "difficult_count_spread": 0,
            "difficult_hours_spread": 0
        }

    @patch("backend.assignment.workload.get_team_workload_summary")
    def test_fairness_worsens(self, mock_summary):
        after_fairness = self.before_fairness.copy()
        after_fairness["high_priority_count_spread"] = 1
        mock_summary.side_effect = [
            {"fairness": self.before_fairness},
            {"fairness": after_fairness}
        ]
        warnings = validate_fairness(self.employees, self.tasks, self.proposed_tasks, self.today)
        self.assertIn("High-priority task distribution becomes less balanced.", warnings)

    @patch("backend.assignment.workload.get_team_workload_summary")
    def test_fairness_unchanged(self, mock_summary):
        mock_summary.return_value = {"fairness": self.before_fairness}
        warnings = validate_fairness(self.employees, self.tasks, self.proposed_tasks, self.today)
        self.assertEqual(warnings, [])

    @patch("backend.assignment.workload.get_team_workload_summary")
    def test_fairness_improves(self, mock_summary):
        before_fairness = self.before_fairness.copy()
        before_fairness["high_priority_count_spread"] = 2
        mock_summary.side_effect = [
            {"fairness": before_fairness},
            {"fairness": self.before_fairness}
        ]
        warnings = validate_fairness(self.employees, self.tasks, self.proposed_tasks, self.today)
        self.assertEqual(warnings, [])

    @patch("backend.assignment.workload.get_team_workload_summary")
    def test_uses_original_and_proposed_tasks(self, mock_summary):
        mock_summary.return_value = {"fairness": self.before_fairness}
        validate_fairness(self.employees, self.tasks, self.proposed_tasks, self.today)
        self.assertEqual(mock_summary.call_count, 2)
        self.assertEqual(
            mock_summary.call_args_list[0].args,
            (self.employees, self.tasks, self.today)
        )
        self.assertEqual(
            mock_summary.call_args_list[1].args,
            (self.employees, self.proposed_tasks, self.today)
        )

class TestFairnessRealData(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 9)
        self.employees = [
            {
                "employee_id": 1,
                "name": "Alex",
                "available_hours": 40,
                "experience_level": "Senior"
            },
            {
                "employee_id": 2,
                "name": "Taylor",
                "available_hours": 40,
                "experience_level": "Senior"
            }
        ]

    def make_task(self, task_id, employee_id, priority="Medium"):
        return {
            "task_id": task_id,
            "title": f"Task {task_id}",
            "employee_id": employee_id,
            "estimated_hours": 5,
            "deadline": "2026-11-13",
            "priority": priority,
            "difficulty": "Easy",
            "status": "Active"
        }

    def test_high_priority_assignment_worsens_fairness(self):
        tasks = [self.make_task(101, 1, "High"), self.make_task(102, None, "High")]
        proposed_tasks = simulate_recommendations(
            tasks,
            [{"task_id": 102, "employee_id": 1}]
        )
        warnings = validate_fairness(self.employees, tasks, proposed_tasks, self.today)
        self.assertIn("High-priority task distribution becomes less balanced.",warnings)

    def test_high_priority_assignment_improves_fairness(self):
        tasks = [
            self.make_task(101, 1, "High"),
            self.make_task(102, 1, "High"),
            self.make_task(103, None, "High")
        ]
        proposed_tasks = simulate_recommendations(
            tasks,
            [{"task_id": 103, "employee_id": 2}]
        )
        warnings = validate_fairness(self.employees, tasks, proposed_tasks, self.today)
        self.assertNotIn("High-priority task distribution becomes less balanced.", warnings)

class TestDuplicateRecommendations(unittest.TestCase):
    def test_no_duplicates(self):
        recommendations = [{"task_id": 101, "employee_id": 1}, {"task_id": 102, "employee_id": 2}]
        duplicates = find_duplicate_task_ids(recommendations)
        self.assertEqual(duplicates, set())

    def test_duplicate_task_with_different_employees(self):
        recommendations = [{"task_id": 101, "employee_id": 1}, {"task_id": 101, "employee_id": 2}]
        duplicates = find_duplicate_task_ids(recommendations)
        self.assertEqual(duplicates, {101})

    def test_duplicate_task_with_same_employee(self):
        recommendations = [{"task_id": 101, "employee_id": 1}, {"task_id": 101, "employee_id": 1}]
        duplicates = find_duplicate_task_ids(recommendations)
        self.assertEqual(duplicates, {101})

    def test_multiple_duplicate_tasks(self):
        recommendations = [
            {"task_id": 101, "employee_id": 1},
            {"task_id": 102, "employee_id": 2},
            {"task_id": 101, "employee_id": 3},
            {"task_id": 102, "employee_id": 1}
        ]
        duplicates = find_duplicate_task_ids(recommendations)
        self.assertEqual(duplicates, {101, 102})

    def test_empty_recommendations(self):
        duplicates = find_duplicate_task_ids([])
        self.assertEqual(duplicates, set())

class TestRecommendationSimulation(unittest.TestCase):
    def setUp(self):
        self.tasks = [
            {"task_id": 101, "employee_id": None},
            {"task_id": 102, "employee_id": None},
            {"task_id": 103, "employee_id": 1}
        ]

    def test_multiple_assignments(self):
        recommendations = [{"task_id": 101, "employee_id": 1}, {"task_id": 102, "employee_id": 2}]
        result = simulate_recommendations(self.tasks, recommendations)
        self.assertEqual(result[0]["employee_id"], 1)
        self.assertEqual(result[1]["employee_id"], 2)
        self.assertEqual(result[2]["employee_id"], 1)

    def test_original_tasks_unchanged(self):
        recommendations = [{"task_id": 101, "employee_id": 2}]
        simulate_recommendations(self.tasks, recommendations)
        self.assertIsNone(self.tasks[0]["employee_id"])

    def test_empty_recommendations(self):
        result = simulate_recommendations(self.tasks, [])
        self.assertEqual(result, self.tasks)
        self.assertIsNot(result, self.tasks)
        self.assertIsNot(result[0], self.tasks[0])


class TestRecommendationValidation(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 9)
        self.employees = [
            {
                "employee_id": 1,
                "name": "Alex",
                "available_hours": 40,
                "experience_level": "Senior"
            },
            {
                "employee_id": 2,
                "name": "Taylor",
                "available_hours": 40,
                "experience_level": "Junior"
            }
        ]
        self.tasks = [
            {
                "task_id": 101,
                "employee_id": None,
                "estimated_hours": 10,
                "deadline": "2026-11-13",
                "priority": "Medium",
                "difficulty": "Easy",
                "status": "Active"
            },
            {
                "task_id": 102,
                "employee_id": None,
                "estimated_hours": 15,
                "deadline": "2026-11-13",
                "priority": "High",
                "difficulty": "Hard",
                "status": "Active"
            }
        ]

    def recommend(self, task_id, employee_id):
        return {
            "task_id": task_id,
            "employee_id": employee_id,
            "reason": "AI recommendation."
        }

    def test_valid_recommendation(self):
        result = validate_recommendations(self.employees, self.tasks, [self.recommend(101, 1)])
        self.assertTrue(result["recommendations"][0]["valid"])
        self.assertEqual(result["recommendations"][0]["errors"], [])

    def test_overdue_task_allowed(self):
        self.tasks[0]["deadline"] = "2026-11-06"
        result = validate_recommendations(self.employees, self.tasks, [self.recommend(101, 1)])
        self.assertTrue(result["recommendations"][0]["valid"])
        self.assertEqual(result["recommendations"][0]["errors"], [])

    def test_invalid_experience_rejected(self):
        result = validate_recommendations(self.employees, self.tasks, [self.recommend(102, 2)])
        self.assertFalse(result["recommendations"][0]["valid"])
        self.assertIn(
            "Junior employees cannot be assigned Hard tasks.",
            result["recommendations"][0]["errors"]
        )

    def test_missing_employee_rejected(self):
        result = validate_recommendations(self.employees, self.tasks,[self.recommend(101, 999)])
        self.assertFalse(result["recommendations"][0]["valid"])

    def test_duplicate_recommendations_rejected(self):
        recommendations = [self.recommend(101, 1),self.recommend(101, 2)]
        result = validate_recommendations(self.employees, self.tasks, recommendations)
        self.assertTrue(
            all(not r["valid"] for r in result["recommendations"])
        )

    def test_completed_task_rejected(self):
        self.tasks[0]["status"] = "Completed"
        result = validate_recommendations(self.employees, self.tasks,[self.recommend(101, 1)])
        self.assertFalse(result["recommendations"][0]["valid"])

    def test_experience_warning_does_not_reject(self):
        self.tasks[0]["difficulty"] = "Medium"
        result = validate_recommendations(self.employees, self.tasks,[self.recommend(101, 2)])
        recommendation = result["recommendations"][0]
        self.assertTrue(recommendation["valid"])
        self.assertIn(
            "Junior employee assigned a Medium task.",
            recommendation["warnings"]
        )

    def test_empty_recommendations(self):
        result = validate_recommendations(self.employees, self.tasks, [])
        self.assertEqual(result["recommendations"], [])

    def test_capacity_not_checked_during_basic_validation(self):
        self.tasks[0]["estimated_hours"] = 50
        result = validate_recommendations(self.employees, self.tasks,[self.recommend(101, 1)])
        self.assertTrue(result["recommendations"][0]["valid"])

class TestSelectedChangesEvaluation(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 9)
        self.employees = [
            {
                "employee_id": 1,
                "name": "Alex",
                "available_hours": 40,
                "experience_level": "Senior"
            },
            {
                "employee_id": 2,
                "name": "Taylor",
                "available_hours": 40,
                "experience_level": "Junior"
            }
        ]
        self.tasks = [
            {
                "task_id": 101,
                "employee_id": None,
                "estimated_hours": 25,
                "deadline": "2026-11-13",
                "priority": "High",
                "difficulty": "Easy",
                "status": "Active"
            },
            {
                "task_id": 102,
                "employee_id": None,
                "estimated_hours": 20,
                "deadline": "2026-11-13",
                "priority": "Medium",
                "difficulty": "Easy",
                "status": "Active"
            }
        ]

    def recommend(self, task_id, employee_id):
        return {
            "task_id": task_id,
            "employee_id": employee_id,
            "reason": "AI recommendation."
        }

    def evaluate(self, recommendations):
        return evaluate_selected_changes(self.employees, self.tasks, recommendations, self.today)

    def test_valid_selection_can_commit(self):
        result = self.evaluate([self.recommend(101, 1)])
        self.assertTrue(result["can_commit"])
        self.assertEqual(result["capacity_errors"], {})

    def test_capacity_conflict_blocks_commit(self):
        result = self.evaluate([self.recommend(101, 1), self.recommend(102, 1)])
        self.assertFalse(result["can_commit"])
        self.assertIn(1, result["capacity_errors"])

    def test_distributing_tasks_allows_commit(self):
        result = self.evaluate([self.recommend(101, 1), self.recommend(102, 2)])
        self.assertTrue(result["can_commit"])
        self.assertEqual(result["capacity_errors"], {})

    def test_invalid_experience_blocks_commit(self):
        self.tasks[0]["difficulty"] = "Hard"
        result = self.evaluate([self.recommend(101, 2)])
        self.assertFalse(result["can_commit"])
        self.assertFalse(result["recommendations"][0]["valid"])

    def test_overdue_selection_with_capacity_conflict_blocks_commit(self):
        self.tasks[0]["deadline"] = "2026-11-06"
        self.tasks[0]["estimated_hours"] = 45
        result = self.evaluate([self.recommend(101, 1)])
        self.assertFalse(result["can_commit"])
        self.assertIn(1, result["capacity_errors"])

    def test_empty_selection_cannot_commit(self):
        result = self.evaluate([])
        self.assertFalse(result["can_commit"])
        self.assertEqual(result["capacity_errors"], {})

    def test_fairness_warning_does_not_block_commit(self):
        result = self.evaluate([self.recommend(101, 1)])
        self.assertTrue(result["can_commit"])
        self.assertIn(
            "High-priority task distribution becomes less balanced.",
            result["fairness_warnings"]
        )

    def test_original_tasks_unchanged(self):
        self.evaluate([self.recommend(101, 1)])
        self.assertIsNone(self.tasks[0]["employee_id"])

    def test_duplicate_selection_blocks_commit(self):
        result = self.evaluate([self.recommend(101, 1), self.recommend(101, 2)])
        self.assertFalse(result["can_commit"])


class TestIndividualRecommendationEvaluation(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 9)
        self.employees = [
            {
                "employee_id": 1,
                "name": "Alex",
                "available_hours": 40,
                "experience_level": "Senior"
            },
            {
                "employee_id": 2,
                "name": "Taylor",
                "available_hours": 40,
                "experience_level": "Junior"
            }
        ]
        self.tasks = [
            {
                "task_id": 101,
                "employee_id": None,
                "estimated_hours": 25,
                "deadline": "2026-11-13",
                "priority": "High",
                "difficulty": "Easy",
                "status": "Active"
            },
            {
                "task_id": 102,
                "employee_id": None,
                "estimated_hours": 20,
                "deadline": "2026-11-13",
                "priority": "Medium",
                "difficulty": "Easy",
                "status": "Active"
            }
        ]

    def recommend(self, task_id, employee_id):
        return {
            "task_id": task_id,
            "employee_id": employee_id,
            "reason": "AI recommendation."
        }

    def evaluate(self, recommendation, selected=None):
        if selected is None:
            selected = []

        return evaluate_individual_recommendation(self.employees, self.tasks, recommendation, selected, self.today)

    def test_valid_recommendation_within_capacity(self):
        result = self.evaluate(self.recommend(101, 1))
        self.assertTrue(result["valid"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["capacity_errors"], {})

    def test_single_recommendation_exceeds_capacity(self):
        self.tasks[0]["estimated_hours"] = 45
        result = self.evaluate(self.recommend(101, 1))
        self.assertTrue(result["valid"])
        self.assertIn(1, result["capacity_errors"])
        self.assertTrue(
            any(
                "5.0 hours" in error
                for error in result["capacity_errors"][1]
            )
        )

    def test_combined_selection_creates_capacity_conflict(self):
        selected = [self.recommend(101, 1)]
        result = self.evaluate(self.recommend(102, 1), selected)
        self.assertTrue(result["valid"])
        self.assertFalse(result["applied"])
        self.assertIn(1, result["capacity_errors"])
        self.assertTrue(
            any(
                "5.0 hours" in error
                for error in result["capacity_errors"][1]
            )
        )

    def test_reassigning_other_task_resolves_conflict(self):
        self.tasks[0]["employee_id"] = 1
        self.tasks[1]["employee_id"] = 1
        selected = [self.recommend(102, 2)]
        result = self.evaluate(self.recommend(101, 1), selected)
        self.assertTrue(result["valid"])
        self.assertEqual(result["capacity_errors"], {})

    def test_existing_selected_conflict_not_attributed_to_new_task(self):
        selected = [self.recommend(101, 1)]
        self.tasks[0]["estimated_hours"] = 45
        result = self.evaluate(self.recommend(102, 2), selected)
        self.assertEqual(result["capacity_errors"], {})

    def test_fairness_warning_for_high_priority_task(self):
        result = self.evaluate(self.recommend(101, 1))
        self.assertIn(
            "High-priority task distribution becomes less balanced.",
            result["fairness_warnings"]
        )

    def test_invalid_experience_rejected(self):
        self.tasks[0]["difficulty"] = "Hard"
        result = self.evaluate(self.recommend(101, 2))
        self.assertFalse(result["valid"])
        self.assertIn(
            "Junior employees cannot be assigned Hard tasks.",
            result["errors"]
        )
        self.assertEqual(result["capacity_errors"], {})
        self.assertEqual(result["fairness_warnings"], [])

    def test_overdue_task_allowed(self):
        self.tasks[0]["deadline"] = "2026-11-06"
        result = self.evaluate(self.recommend(101, 1))
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_experience_warning_does_not_invalidate(self):
        self.tasks[0]["difficulty"] = "Medium"
        result = self.evaluate(self.recommend(101, 2))
        self.assertTrue(result["valid"])
        self.assertIn(
            "Junior employee assigned a Medium task.",
            result["warnings"]
        )

    def test_already_applied_recommendation(self):
        recommendation = self.recommend(101, 1)
        result = self.evaluate(recommendation, [recommendation])
        self.assertTrue(result["applied"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["capacity_errors"], {})

    def test_applied_recommendation_evaluates_its_impact(self):
        first = self.recommend(101, 1)
        second = self.recommend(102, 1)
        result = self.evaluate(second, [first, second])
        self.assertTrue(result["applied"])
        self.assertIn(1, result["capacity_errors"])

    def test_original_tasks_unchanged(self):
        recommendation = self.recommend(101, 1)
        self.evaluate(recommendation)
        self.assertIsNone(self.tasks[0]["employee_id"])
        self.assertIsNone(self.tasks[1]["employee_id"])


if __name__ == "__main__":
    unittest.main()