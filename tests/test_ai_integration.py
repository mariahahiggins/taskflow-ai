import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import date

from backend.ai_integration import (
    format_task_information,
    find_unresolved_tasks,
    evaluate_ai_batch,
    generate_task_recommendations
)

class TestFormatTaskInformation(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {"employee_id": 1, "name": "Sarah", "status": "Active"},
            {"employee_id": 2, "name": "James", "status": "Inactive"},
            {"employee_id": 3, "name": "Alex", "status": "Active"}
        ]
        self.tasks = [
            {"task_id": 101, "status": "Active", "employee_id": None},
            {"task_id": 102, "status": "Completed", "employee_id": 2}
        ]
        self.workload_summary = {"total_employees": 2}
        self.eligible_task_ids = [101]

    @patch("backend.ai_integration.date")
    def test_inactive_employees_excluded(self, mock_date):
        mock_date.today.return_value.isoformat.return_value = "2026-11-09"
        result = format_task_information(
            self.employees,
            self.tasks,
            self.workload_summary,
            self.eligible_task_ids
        )
        data = json.loads(result)
        self.assertEqual(
            [employee["employee_id"] for employee in data["employees"]],
            [1, 3]
        )
        self.assertEqual(len(data["tasks"]), 2)
        self.assertEqual(data["eligible_task_ids"], [101])
        self.assertEqual(data["employee_workloads"], [])
        self.assertEqual(data["fairness"], {})
        self.assertEqual(data["today"], "2026-11-09")

    def test_all_employees_inactive(self):
        for employee in self.employees:
            employee["status"] = "Inactive"
        result = format_task_information(
            self.employees,
            self.tasks,
            self.workload_summary,
            self.eligible_task_ids
        )
        data = json.loads(result)
        self.assertEqual(data["employees"], [])

    def test_original_employees_not_modified(self):
        original = [employee.copy() for employee in self.employees]
        format_task_information(
            self.employees,
            self.tasks,
            self.workload_summary,
            self.eligible_task_ids
        )
        self.assertEqual(self.employees, original)


class TestFindUnresolvedTasks(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {
                "employee_id": 1,
                "name": "Alex",
                "experience_level": "Junior",
                "status": "Active",
            },
            {
                "employee_id": 2,
                "name": "Sarah",
                "experience_level": "Senior",
                "status": "Active",
            },
        ]
        self.tasks = [
            {
                "task_id": 101,
                "status": "Active",
                "employee_id": 1,
                "difficulty": "Hard",
            },
            {
                "task_id": 102,
                "status": "Active",
                "employee_id": None,
                "difficulty": "Easy",
            },
            {
                "task_id": 103,
                "status": "Completed",
                "employee_id": 1,
                "difficulty": "Hard",
            },
        ]
        self.eligible_task_ids = [101, 102]

    def test_detects_junior_assigned_hard_task(self):
        result = find_unresolved_tasks(self.employees, self.tasks, [], self.eligible_task_ids,)
        self.assertIn(
            {
                "task_id": 101,
                "problem": "Hard task remains assigned to a Junior employee.",
            },
            result,
        )

    def test_detects_unassigned_task(self):
        result = find_unresolved_tasks(self.employees, self.tasks, [], self.eligible_task_ids,)
        self.assertIn(
            {
                "task_id": 102,
                "problem": "Task remains unassigned.",
            },
            result,
        )

    def test_resolved_tasks_not_reported(self):
        recommendations = [
            {"task_id": 101, "employee_id": 2, "reason": "Senior experience"},
            {"task_id": 102, "employee_id": 2, "reason": "Available employee"},
        ]
        result = find_unresolved_tasks(self.employees, self.tasks, recommendations,self.eligible_task_ids,)
        self.assertEqual(result, [])

    def test_completed_tasks_ignored(self):
        result = find_unresolved_tasks(self.employees, self.tasks, [], [103])
        self.assertEqual(result, [])



class TestEvaluateAIBatch(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {
                "employee_id": 1,
                "name": "Alex",
                "experience_level": "Junior",
                "status": "Active",
            },
            {
                "employee_id": 2,
                "name": "Sarah",
                "experience_level": "Senior",
                "status": "Active",
            },
        ]
        self.tasks = [
            {
                "task_id": 101,
                "status": "Active",
                "employee_id": 1,
                "difficulty": "Hard",
            },
            {
                "task_id": 102,
                "status": "Active",
                "employee_id": 2,
                "difficulty": "Easy",
            },
        ]
        self.eligible_task_ids = [101, 102]
        self.today = date(2026, 11, 16)

    @patch("backend.ai_integration.assignment.evaluate_selected_changes")
    def test_detects_same_employee_assignment(self, mock_evaluate):
        mock_evaluate.return_value = {
            "recommendations": [{"valid": True}],
            "capacity_errors": {},
            "fairness_warnings": [],
        }
        recommendations = [
            {"task_id": 102, "employee_id": 2, "reason": "No change"}
        ]
        result = evaluate_ai_batch(self.employees, self.tasks, recommendations, self.eligible_task_ids, self.today,)
        self.assertEqual(result["same_employee_task_ids"], [102])

    @patch("backend.ai_integration.assignment.evaluate_selected_changes")
    def test_detects_duplicate_task_ids(self, mock_evaluate):
        mock_evaluate.return_value = {
            "recommendations": [{"valid": True}, {"valid": True}],
            "capacity_errors": {},
            "fairness_warnings": [],
        }
        recommendations = [
            {"task_id": 101, "employee_id": 2, "reason": "First"},
            {"task_id": 101, "employee_id": 2, "reason": "Duplicate"},
        ]
        result = evaluate_ai_batch(self.employees, self.tasks, recommendations, self.eligible_task_ids, self.today,)
        self.assertEqual(result["duplicate_task_ids"], [101])

    @patch("backend.ai_integration.assignment.evaluate_selected_changes")
    def test_detects_ineligible_task(self, mock_evaluate):
        mock_evaluate.return_value = {
            "recommendations": [{"valid": True}],
            "capacity_errors": {},
            "fairness_warnings": [],
        }
        recommendations = [
            {"task_id": 102, "employee_id": 1, "reason": "Not eligible"}
        ]
        result = evaluate_ai_batch(self.employees, self.tasks, recommendations,[101], self.today,)
        self.assertEqual(result["invalid_task_ids"], [102])

    @patch("backend.ai_integration.assignment.evaluate_selected_changes")
    def test_preserves_capacity_errors(self, mock_evaluate):
        mock_evaluate.return_value = {
            "recommendations": [{"valid": True}],
            "capacity_errors": {
                "2": ["Proposed assignments worsen capacity by 8.0 hours."]
            },
            "fairness_warnings": [],
        }
        recommendations = [
            {"task_id": 101, "employee_id": 2, "reason": "Reassign"}
        ]
        result = evaluate_ai_batch(self.employees, self.tasks, recommendations, self.eligible_task_ids, self.today,)
        self.assertEqual(
            result["capacity_errors"],
            {"2": ["Proposed assignments worsen capacity by 8.0 hours."]},
        )

    @patch("backend.ai_integration.assignment.evaluate_selected_changes")
    def test_reports_unresolved_experience_violation(self, mock_evaluate):
        mock_evaluate.return_value = {
            "recommendations": [],
            "capacity_errors": {},
            "fairness_warnings": [],
        }
        result = evaluate_ai_batch(self.employees, self.tasks, [], self.eligible_task_ids, self.today,)
        self.assertEqual(
            result["unresolved_tasks"],
            [{
                "task_id": 101,
                "problem": "Hard task remains assigned to a Junior employee.",
            }],
        )


@patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
class TestGenerateTaskRecommendations(unittest.TestCase):
    def setUp(self):
        self.task_information = json.dumps({
            "today": "2026-11-16",
            "employees": [
                {
                    "employee_id": 1,
                    "name": "Alex",
                    "status": "Active",
                    "experience_level": "Junior",
                },
                {
                    "employee_id": 2,
                    "name": "Sarah",
                    "status": "Active",
                    "experience_level": "Senior",
                },
            ],
            "tasks": [
                {
                    "task_id": 101,
                    "status": "Active",
                    "employee_id": 1,
                    "difficulty": "Hard",
                }
            ],
            "eligible_task_ids": [101],
        })
        self.valid_response = {
            "recommendations": [
                {
                    "task_id": 101,
                    "employee_id": 2,
                    "reason": "Sarah has suitable experience.",
                }
            ],
            "debug_reason": "Corrected the experience violation.",
        }
        self.invalid_response = {
            "recommendations": [
                {
                    "task_id": 101,
                    "employee_id": 1,
                    "reason": "Keep Alex assigned.",
                }
            ],
            "debug_reason": "Initial recommendation.",
        }
        self.valid_feedback = {
            "invalid_task_ids": [],
            "recommendation_validation": [{"valid": True}],
            "capacity_errors": {},
            "fairness_warnings": [],
            "unresolved_tasks": [],
            "same_employee_task_ids": [],
            "duplicate_task_ids": [],
        }
        self.invalid_feedback = {
            **self.valid_feedback,
            "capacity_errors": {
                "1": ["Proposed assignment worsens capacity."]
            },
        }

    def make_gemini_response(self, data):
        response = MagicMock()
        response.text = json.dumps(data)
        return response

    @patch("backend.ai_integration.evaluate_ai_batch")
    @patch("backend.ai_integration.genai.Client")
    def test_valid_response_does_not_trigger_revision(self, mock_client, mock_evaluate):
        mock_client.return_value.models.generate_content.return_value = (self.make_gemini_response(self.valid_response))
        mock_evaluate.return_value = self.valid_feedback
        result = generate_task_recommendations(self.task_information)
        self.assertEqual(result, self.valid_response)
        self.assertEqual(mock_client.return_value.models.generate_content.call_count, 1)
        self.assertEqual(mock_evaluate.call_count, 2)

    @patch("backend.ai_integration.evaluate_ai_batch")
    @patch("backend.ai_integration.genai.Client")
    def test_capacity_conflict_triggers_revision(self, mock_client, mock_evaluate):
        mock_client.return_value.models.generate_content.side_effect = [
            self.make_gemini_response(self.invalid_response),
            self.make_gemini_response(self.valid_response)
        ]
        mock_evaluate.side_effect = [self.invalid_feedback, self.valid_feedback,]
        result = generate_task_recommendations(self.task_information)
        self.assertEqual(result, self.valid_response)
        self.assertEqual(mock_client.return_value.models.generate_content.call_count, 2)
        revision_prompt = (mock_client.return_value.models.generate_content.call_args_list[1].kwargs["contents"])
        self.assertIn("capacity_errors", revision_prompt)
        self.assertIn("worsens capacity", revision_prompt)

    @patch("backend.ai_integration.evaluate_ai_batch")
    @patch("backend.ai_integration.genai.Client")
    def test_unresolved_task_triggers_revision(self, mock_client, mock_evaluate):
        empty_response = {
            "recommendations": [],
            "debug_reason": "No assignments found."
        }
        unresolved_feedback = {
            **self.valid_feedback,
            "unresolved_tasks": [
                {
                    "task_id": 101,
                    "problem": "Hard task remains assigned to a Junior employee."
                }
            ],
        }
        mock_client.return_value.models.generate_content.side_effect = [
            self.make_gemini_response(empty_response),
            self.make_gemini_response(self.valid_response)
        ]
        mock_evaluate.side_effect = [
            unresolved_feedback,
            self.valid_feedback
        ]
        result = generate_task_recommendations(self.task_information)
        self.assertEqual(result, self.valid_response)
        self.assertEqual(mock_client.return_value.models.generate_content.call_count, 2)

    @patch("backend.ai_integration.evaluate_ai_batch")
    @patch("backend.ai_integration.genai.Client")
    def test_same_employee_recommendation_triggers_revision(self, mock_client, mock_evaluate):
        same_employee_feedback = {
            **self.valid_feedback,
            "same_employee_task_ids": [101]
        }
        mock_client.return_value.models.generate_content.side_effect = [
            self.make_gemini_response(self.invalid_response),
            self.make_gemini_response(self.valid_response)
        ]
        mock_evaluate.side_effect = [
            same_employee_feedback,
            self.valid_feedback
        ]
        result = generate_task_recommendations(self.task_information)
        self.assertEqual(result, self.valid_response)
        self.assertEqual(mock_client.return_value.models.generate_content.call_count, 2)

    @patch("backend.ai_integration.evaluate_ai_batch")
    @patch("backend.ai_integration.genai.Client")
    def test_duplicate_recommendations_trigger_revision(self, mock_client, mock_evaluate):
        duplicate_feedback = {
            **self.valid_feedback,
            "duplicate_task_ids": [101]
        }
        mock_client.return_value.models.generate_content.side_effect = [
            self.make_gemini_response(self.invalid_response),
            self.make_gemini_response(self.valid_response)
        ]
        mock_evaluate.side_effect = [
            duplicate_feedback,
            self.valid_feedback
        ]
        result = generate_task_recommendations(self.task_information)
        self.assertEqual(result, self.valid_response)
        self.assertEqual(mock_client.return_value.models.generate_content.call_count, 2)

    @patch("backend.ai_integration.evaluate_ai_batch")
    @patch("backend.ai_integration.genai.Client")
    def test_revision_failure_uses_initial_response(self, mock_client, mock_evaluate):
        mock_client.return_value.models.generate_content.side_effect = [
            self.make_gemini_response(self.invalid_response),
            Exception("503 UNAVAILABLE"),
        ]
        mock_evaluate.return_value = self.invalid_feedback
        result = generate_task_recommendations(self.task_information)
        self.assertEqual(result, self.invalid_response)
        self.assertEqual(mock_client.return_value.models.generate_content.call_count, 2)
        self.assertEqual(mock_evaluate.call_count, 2)

    @patch("backend.ai_integration.evaluate_ai_batch")
    @patch("backend.ai_integration.genai.Client")
    def test_fairness_warning_does_not_trigger_revision(self, mock_client, mock_evaluate):
        fairness_feedback = {
            **self.valid_feedback,
            "fairness_warnings": [
                "Two-week workload balance becomes less balanced."
            ],
        }
        mock_client.return_value.models.generate_content.return_value = (self.make_gemini_response(self.valid_response))
        mock_evaluate.return_value = fairness_feedback
        result = generate_task_recommendations(self.task_information)
        self.assertEqual(result, self.valid_response)
        self.assertEqual(mock_client.return_value.models.generate_content.call_count, 1)

    @patch("backend.ai_integration.evaluate_ai_batch")
    @patch("backend.ai_integration.genai.Client")
    def test_invalid_revised_response_is_validated_again(self, mock_client, mock_evaluate):
        mock_client.return_value.models.generate_content.side_effect = [
            self.make_gemini_response(self.invalid_response),
            self.make_gemini_response(self.invalid_response)
        ]
        mock_evaluate.return_value = self.invalid_feedback
        result = generate_task_recommendations(self.task_information)
        self.assertEqual(result, self.invalid_response)
        self.assertEqual(mock_evaluate.call_count, 2)
        self.assertEqual(mock_client.return_value.models.generate_content.call_count, 2)


if __name__ == "__main__":
    unittest.main()