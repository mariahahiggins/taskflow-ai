import unittest

from backend.fairness import (
    calculate_utilization_spread,
    count_high_priority_tasks,
    count_difficult_tasks,
    calculate_team_fairness
)

class TestUtilizationSpread(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {
                "employee_id": 1,
                "one_week_utilization": 80.0,
                "two_week_utilization": 70.0
            },
            {
                "employee_id": 2,
                "one_week_utilization": 40.0,
                "two_week_utilization": 50.0
            },
            {
                "employee_id": 3,
                "one_week_utilization": 60.0,
                "two_week_utilization": 60.0
            }
        ]

    def test_one_week_spread(self):
        result = calculate_utilization_spread(self.employees, "one_week")
        self.assertEqual(result, 40.0)

    def test_two_week_spread(self):
        result = calculate_utilization_spread(self.employees, "two_week")
        self.assertEqual(result, 20.0)

    def test_equal_utilization(self):
        employees = [
            {"one_week_utilization": 50.0},
            {"one_week_utilization": 50.0},
            {"one_week_utilization": 50.0}
        ]
        result = calculate_utilization_spread(employees, "one_week")
        self.assertEqual(result, 0.0)

    def test_none_utilization_excluded(self):
        employees = [
            {"one_week_utilization": 80.0},
            {"one_week_utilization": None},
            {"one_week_utilization": 40.0}
        ]
        result = calculate_utilization_spread(employees, "one_week")
        self.assertEqual(result, 40.0)

    def test_all_none_utilization(self):
        employees = [
            {"one_week_utilization": None},
            {"one_week_utilization": None}
        ]
        result = calculate_utilization_spread(employees, "one_week")
        self.assertIsNone(result)

    def test_single_employee(self):
        employees = [{"one_week_utilization": 75.0}]
        result = calculate_utilization_spread(employees, "one_week")
        self.assertIsNone(result)

    def test_empty_team(self):
        result = calculate_utilization_spread([], "one_week")
        self.assertIsNone(result)

    def test_over_capacity_utilization(self):
        employees = [
            {"one_week_utilization": 150.0},
            {"one_week_utilization": 50.0}
        ]
        result = calculate_utilization_spread(employees, "one_week")
        self.assertEqual(result, 100.0)

    def test_fractional_utilization(self):
        employees = [
            {"one_week_utilization": 33.3},
            {"one_week_utilization": 66.7}
        ]

        result = calculate_utilization_spread(employees, "one_week")
        self.assertAlmostEqual(result, 33.4)

    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            calculate_utilization_spread(self.employees, "three_week")


class TestHighPriorityTasks(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {"employee_id": 1, "name": "Sarah"},
            {"employee_id": 2, "name": "James"},
            {"employee_id": 3, "name": "Alex"}
        ]

    def make_task(self, hours, priority="High", status="Active", employee_id=1):
        return {
            "estimated_hours": hours,
            "priority": priority,
            "status": status,
            "employee_id": employee_id
        }

    def test_single_high_priority_task(self):
        tasks = [self.make_task(10)]
        result = count_high_priority_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 10})

    def test_multiple_tasks_same_employee(self):
        tasks = [
            self.make_task(5), 
            self.make_task(8), 
            self.make_task(3)
        ]
        result = count_high_priority_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 3, "hours": 16})

    def test_tasks_distributed_across_employees(self):
        tasks = [
            self.make_task(10, employee_id=1),
            self.make_task(5, employee_id=2),
            self.make_task(8, employee_id=2)
        ]
        result = count_high_priority_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 10})
        self.assertEqual(result[2], {"count": 2, "hours": 13})
        self.assertEqual(result[3], {"count": 0, "hours": 0})

    def test_low_and_medium_priority_excluded(self):
        tasks = [
            self.make_task(10, priority="Low"),
            self.make_task(8, priority="Medium"),
            self.make_task(5, priority="High")
        ]
        result = count_high_priority_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 5})

    def test_completed_high_priority_excluded(self):
        tasks = [
            self.make_task(10, status="Completed"),
            self.make_task(5)
        ]
        result = count_high_priority_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 5})

    def test_unassigned_tasks_excluded(self):
        tasks = [
            self.make_task(10, employee_id=None),
            self.make_task(5, employee_id=1)
        ]
        result = count_high_priority_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 5})
        self.assertNotIn(None, result)

    def test_unknown_employee_excluded(self):
        tasks = [
            self.make_task(10, employee_id=99),
            self.make_task(5, employee_id=1)
        ]
        result = count_high_priority_tasks(self.employees, tasks)
        self.assertNotIn(99, result)
        self.assertEqual(result[1], {"count": 1, "hours": 5})

    def test_fractional_hours(self):
        tasks = [
            self.make_task(2.5),
            self.make_task(7.75)
        ]
        result = count_high_priority_tasks(self.employees, tasks)
        self.assertEqual(result[1]["count"], 2)
        self.assertAlmostEqual(result[1]["hours"], 10.25)

    def test_empty_tasks(self):
        result = count_high_priority_tasks(self.employees, [])
        self.assertEqual(
            result,
            {
                1: {"count": 0, "hours": 0},
                2: {"count": 0, "hours": 0},
                3: {"count": 0, "hours": 0}
            }
        )

    def test_empty_employees(self):
        tasks = [self.make_task(10)]
        result = count_high_priority_tasks([], tasks)
        self.assertEqual(result, {})

    def test_all_tasks_completed(self):
        tasks = [
            self.make_task(10, status="Completed"),
            self.make_task(5, status="Completed")
        ]
        result = count_high_priority_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 0, "hours": 0})

    def test_original_tasks_not_modified(self):
        tasks = [
            self.make_task(10),
            self.make_task(5, employee_id=2)
        ]
        original_tasks = [task.copy() for task in tasks]
        count_high_priority_tasks(self.employees, tasks)
        self.assertEqual(tasks, original_tasks)


class TestDifficultTasks(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {"employee_id": 1, "name": "Sarah"},
            {"employee_id": 2, "name": "James"},
            {"employee_id": 3, "name": "Alex"}
        ]

    def make_task(self, hours, difficulty="Hard", status="Active", employee_id=1):
        return {
            "estimated_hours": hours,
            "difficulty": difficulty,
            "status": status,
            "employee_id": employee_id
        }

    def test_single_hard_task(self):
        tasks = [self.make_task(10)]
        result = count_difficult_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 10})

    def test_multiple_hard_tasks_same_employee(self):
        tasks = [
            self.make_task(5),
            self.make_task(8),
            self.make_task(3)
        ]
        result = count_difficult_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 3, "hours": 16})

    def test_tasks_distributed_across_employees(self):
        tasks = [
            self.make_task(10, employee_id=1),
            self.make_task(5, employee_id=2),
            self.make_task(8, employee_id=2)
        ]
        result = count_difficult_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 10})
        self.assertEqual(result[2], {"count": 2, "hours": 13})
        self.assertEqual(result[3], {"count": 0, "hours": 0})

    def test_easy_and_medium_tasks_excluded(self):
        tasks = [
            self.make_task(10, difficulty="Easy"),
            self.make_task(8, difficulty="Medium"),
            self.make_task(5, difficulty="Hard")
        ]
        result = count_difficult_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 5})

    def test_completed_hard_tasks_excluded(self):
        tasks = [
            self.make_task(10, status="Completed"),
            self.make_task(5)
        ]
        result = count_difficult_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 5})

    def test_unassigned_tasks_excluded(self):
        tasks = [
            self.make_task(10, employee_id=None),
            self.make_task(5, employee_id=1)
        ]
        result = count_difficult_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 1, "hours": 5})
        self.assertNotIn(None, result)

    def test_unknown_employee_excluded(self):
        tasks = [
            self.make_task(10, employee_id=99),
            self.make_task(5, employee_id=1)
        ]
        result = count_difficult_tasks(self.employees, tasks)
        self.assertNotIn(99, result)
        self.assertEqual(result[1], {"count": 1, "hours": 5})

    def test_fractional_hours(self):
        tasks = [
            self.make_task(2.5),
            self.make_task(7.75)
        ]
        result = count_difficult_tasks(self.employees, tasks)
        self.assertEqual(result[1]["count"], 2)
        self.assertAlmostEqual(result[1]["hours"], 10.25)

    def test_empty_tasks(self):
        result = count_difficult_tasks(self.employees, [])
        self.assertEqual(
            result,
            {
                1: {"count": 0, "hours": 0},
                2: {"count": 0, "hours": 0},
                3: {"count": 0, "hours": 0}
            }
        )

    def test_empty_employees(self):
        tasks = [self.make_task(10)]
        result = count_difficult_tasks([], tasks)
        self.assertEqual(result, {})

    def test_all_tasks_completed(self):
        tasks = [
            self.make_task(10, status="Completed"),
            self.make_task(5, status="Completed")
        ]
        result = count_difficult_tasks(self.employees, tasks)
        self.assertEqual(result[1], {"count": 0, "hours": 0})

    def test_original_tasks_not_modified(self):
        tasks = [
            self.make_task(10),
            self.make_task(5, employee_id=2)
        ]
        original_tasks = [task.copy() for task in tasks]
        count_difficult_tasks(self.employees, tasks)
        self.assertEqual(tasks, original_tasks)


class TestTeamFairness(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {"employee_id": 1, "name": "Sarah"},
            {"employee_id": 2, "name": "James"},
            {"employee_id": 3, "name": "Alex"}
        ]
        self.employee_summaries = [
            {
                "employee_id": 1,
                "one_week_utilization": 80.0,
                "two_week_utilization": 70.0
            },
            {
                "employee_id": 2,
                "one_week_utilization": 40.0,
                "two_week_utilization": 50.0
            },
            {
                "employee_id": 3,
                "one_week_utilization": 60.0,
                "two_week_utilization": 60.0
            }
        ]

    def make_task(self, hours, priority="Low", difficulty="Easy", status="Active", employee_id=1):
        return {
            "estimated_hours": hours,
            "priority": priority,
            "difficulty": difficulty,
            "status": status,
            "employee_id": employee_id
        }

    def test_utilization_spreads(self):
        result = calculate_team_fairness(self.employees, [], self.employee_summaries)
        self.assertEqual(result["one_week_utilization_spread"], 40.0)
        self.assertEqual(result["two_week_utilization_spread"], 20.0)

    def test_high_priority_distribution(self):
        tasks = [
            self.make_task(10, priority="High", employee_id=1),
            self.make_task(5, priority="High", employee_id=1),
            self.make_task(8, priority="High", employee_id=2)
        ]
        result = calculate_team_fairness(self.employees, tasks, self.employee_summaries)
        self.assertEqual(
            result["high_priority_tasks"][1],
            {"count": 2, "hours": 15}
        )
        self.assertEqual(
            result["high_priority_tasks"][2],
            {"count": 1, "hours": 8}
        )
        self.assertEqual(
            result["high_priority_tasks"][3],
            {"count": 0, "hours": 0}
        )
        self.assertEqual(result["high_priority_count_spread"], 2)
        self.assertEqual(result["high_priority_hours_spread"], 15)

    def test_difficult_task_distribution(self):
        tasks = [
            self.make_task(12, difficulty="Hard", employee_id=1),
            self.make_task(8, difficulty="Hard", employee_id=2),
            self.make_task(5, difficulty="Hard", employee_id=2)
        ]
        result = calculate_team_fairness(self.employees, tasks, self.employee_summaries)
        self.assertEqual(
            result["difficult_tasks"][1],
            {"count": 1, "hours": 12}
        )
        self.assertEqual(
            result["difficult_tasks"][2],
            {"count": 2, "hours": 13}
        )
        self.assertEqual(
            result["difficult_tasks"][3],
            {"count": 0, "hours": 0}
        )
        self.assertEqual(result["difficult_count_spread"], 2)
        self.assertEqual(result["difficult_hours_spread"], 13)

    def test_priority_and_difficulty_are_independent(self):
        tasks = [
            self.make_task(10, priority="High", difficulty="Easy"),
            self.make_task(8, priority="Low", difficulty="Hard")
        ]
        result = calculate_team_fairness(self.employees, tasks, self.employee_summaries)
        self.assertEqual(
            result["high_priority_tasks"][1],
            {"count": 1, "hours": 10}
        )
        self.assertEqual(
            result["difficult_tasks"][1],
            {"count": 1, "hours": 8}
        )

    def test_completed_and_unassigned_tasks_excluded(self):
        tasks = [
            self.make_task(10, priority="High", difficulty="Hard", status="Completed"),
            self.make_task(8, priority="High", difficulty="Hard", employee_id=None)
        ]
        result = calculate_team_fairness(self.employees, tasks, self.employee_summaries)
        self.assertEqual(
            result["high_priority_tasks"][1],
            {"count": 0, "hours": 0}
        )
        self.assertEqual(
            result["difficult_tasks"][1],
            {"count": 0, "hours": 0}
        )

    def test_equal_distribution(self):
        tasks = [
            self.make_task(5, priority="High", difficulty="Hard",employee_id=1),
            self.make_task(5, priority="High", difficulty="Hard",employee_id=2),
            self.make_task(5, priority="High", difficulty="Hard",employee_id=3)]
        result = calculate_team_fairness(self.employees, tasks, self.employee_summaries)
        self.assertEqual(result["high_priority_count_spread"], 0)
        self.assertEqual(result["high_priority_hours_spread"], 0)
        self.assertEqual(result["difficult_count_spread"], 0)
        self.assertEqual(result["difficult_hours_spread"], 0)

    def test_no_tasks(self):
        result = calculate_team_fairness(self.employees, [], self.employee_summaries)
        self.assertEqual(result["high_priority_count_spread"], 0)
        self.assertEqual(result["high_priority_hours_spread"], 0)
        self.assertEqual(result["difficult_count_spread"], 0)
        self.assertEqual(result["difficult_hours_spread"], 0)

    def test_empty_team(self):
        result = calculate_team_fairness([], [], [])
        self.assertIsNone(result["one_week_utilization_spread"])
        self.assertIsNone(result["two_week_utilization_spread"])
        self.assertEqual(result["high_priority_tasks"], {})
        self.assertEqual(result["difficult_tasks"], {})
        self.assertIsNone(result["high_priority_count_spread"])
        self.assertIsNone(result["high_priority_hours_spread"])
        self.assertIsNone(result["difficult_count_spread"])
        self.assertIsNone(result["difficult_hours_spread"])

    def test_single_employee(self):
        employees = [self.employees[0]]
        summaries = [self.employee_summaries[0]]
        tasks = [self.make_task(10, priority="High", difficulty="Hard")]
        result = calculate_team_fairness(employees, tasks, summaries)
        self.assertIsNone(result["one_week_utilization_spread"])
        self.assertIsNone(result["high_priority_count_spread"])
        self.assertIsNone(result["difficult_hours_spread"])
        self.assertEqual(
            result["high_priority_tasks"][1],
            {"count": 1, "hours": 10}
        )

    def test_zero_availability_excluded_from_spread(self):
        summaries = [
            {
                "employee_id": 1,
                "one_week_utilization": 80.0,
                "two_week_utilization": 70.0
            },
            {
                "employee_id": 2,
                "one_week_utilization": None,
                "two_week_utilization": None
            },
            {
                "employee_id": 3,
                "one_week_utilization": 40.0,
                "two_week_utilization": 50.0
            }
        ]
        result = calculate_team_fairness(self.employees, [], summaries)
        self.assertEqual(result["one_week_utilization_spread"], 40.0)
        self.assertEqual(result["two_week_utilization_spread"], 20.0)

    def test_fractional_hours_spread(self):
        tasks = [
            self.make_task(2.5, priority="High", difficulty="Hard", employee_id=1),
            self.make_task(7.75, priority="High", difficulty="Hard", employee_id=2)
        ]
        result = calculate_team_fairness(self.employees, tasks, self.employee_summaries)
        self.assertAlmostEqual(result["high_priority_hours_spread"], 7.75)
        self.assertAlmostEqual(result["difficult_hours_spread"], 7.75)

    def test_original_inputs_not_modified(self):
        tasks = [self.make_task(10, priority="High", difficulty="Hard")]
        original_employees = [employee.copy() for employee in self.employees]
        original_summaries = [summary.copy() for summary in self.employee_summaries]
        original_tasks = [task.copy() for task in tasks]
        calculate_team_fairness(self.employees, tasks, self.employee_summaries)
        self.assertEqual(self.employees, original_employees)
        self.assertEqual(self.employee_summaries, original_summaries)
        self.assertEqual(tasks, original_tasks)

