import unittest
from unittest.mock import patch, Mock

import requests

from frontend import api_client

class TestAPIClient(unittest.TestCase):
    """Test HTTP requests made by the shared frontend API client."""

    def setUp(self):
        """Create a mocked HTTP response for each test."""
        self.response = Mock()
        self.response.json.return_value = {"success": True}
        self.patcher = patch(
            "frontend.api_client.requests.request",
            return_value=self.response
        )
        self.mock_request = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def assert_api_call(self, method, endpoint, data=None):
        """Check the method, URL, JSON body, and timeout."""
        expected_timeout = (
            60 if endpoint == "/recommendations" else 10
        )
        self.mock_request.assert_called_once_with(
            method,
            f"{api_client.API_BASE_URL}{endpoint}",
            json=data,
            timeout=expected_timeout
        )
        self.response.raise_for_status.assert_called_once()
        self.response.json.assert_called_once()

    def test_get_employees(self):
        result = api_client.get_employees()
        self.assert_api_call("GET", "/employees")
        self.assertEqual(result, {"success": True})

    def test_get_employee(self):
        api_client.get_employee(3)
        self.assert_api_call("GET", "/employees/3")

    def test_create_employee(self):
        data = {
            "name": "Sarah",
            "available_hours": 40,
            "experience_level": "Senior"
        }
        api_client.create_employee(data)
        self.assert_api_call("POST", "/employees", data)

    def test_update_employee(self):
        data = {
            "name": "Sarah",
            "available_hours": 30,
            "experience_level": "Senior",
            "status": "Active"
        }
        api_client.update_employee(1, data)
        self.assert_api_call("PUT", "/employees/1", data)

    def test_deactivate_employee(self):
        data = {
            "name": "Sarah",
            "available_hours": 30,
            "experience_level": "Senior",
            "status": "Inactive"
        }
        api_client.update_employee(1, data)
        self.assert_api_call("PUT", "/employees/1", data)

    def test_reactivate_employee(self):
        data = {
            "name": "Sarah",
            "available_hours": 30,
            "experience_level": "Senior",
            "status": "Active"
        }

        api_client.update_employee(1, data)
        self.assert_api_call("PUT", "/employees/1", data)

    def test_get_tasks(self):
        api_client.get_tasks()
        self.assert_api_call("GET", "/tasks")

    def test_get_task(self):
        api_client.get_task(5)
        self.assert_api_call("GET", "/tasks/5")

    def test_create_task(self):
        data = {
            "title": "Prepare report",
            "estimated_hours": 8,
            "deadline": "2026-11-20",
            "priority": "High",
            "difficulty": "Medium",
            "employee_id": None
        }
        api_client.create_task(data)
        self.assert_api_call("POST", "/tasks", data)

    def test_update_task(self):
        data = {
            "title": "Updated report",
            "estimated_hours": 10
        }
        api_client.update_task(2, data)
        self.assert_api_call("PUT", "/tasks/2", data)

    def test_get_workloads(self):
        api_client.get_workloads()
        self.assert_api_call("GET", "/workloads")

    def test_get_employee_workload(self):
        api_client.get_employee_workload(2)
        self.assert_api_call(
            "GET",
            "/employees/2/workload"
        )

    def test_generate_recommendations(self):
        result = api_client.generate_recommendations()
        self.assert_api_call(
            "POST",
            "/recommendations"
        )
        self.assertEqual(result, {"success": True})

    def test_preview_recommendation(self):
        data = {
            "recommendation": {
                "task_id": 6,
                "employee_id": 1
            },
            "selected_recommendations": []
        }
        api_client.preview_recommendation(data)
        self.assert_api_call(
            "POST",
            "/recommendations/preview",
            data
        )

    def test_evaluate_recommendations(self):
        data = {
            "selected_recommendations": [
                {"task_id": 6, "employee_id": 1}
            ]
        }
        api_client.evaluate_recommendations(data)
        self.assert_api_call(
            "POST",
            "/recommendations/evaluate",
            data
        )

    def test_approve_recommendations(self):
        data = {
            "selected_recommendations": [
                {"task_id": 6, "employee_id": 1}
            ]
        }
        api_client.approve_recommendations(data)
        self.assert_api_call(
            "POST",
            "/recommendations/approve",
            data
        )

    def test_returns_decoded_json(self):
        expected = [
            {"employee_id": 1, "name": "Sarah"},
            {"employee_id": 2, "name": "James"}
        ]
        self.response.json.return_value = expected
        result = api_client.get_employees()
        self.assertEqual(result, expected)

    def test_http_error_propagates(self):
        self.response.raise_for_status.side_effect = (
            requests.HTTPError("400 Bad Request")
        )
        with self.assertRaises(requests.HTTPError):
            api_client.get_tasks()
        self.response.json.assert_not_called()

    def test_connection_error_propagates(self):
        self.mock_request.side_effect = (
            requests.ConnectionError("Connection refused")
        )
        with self.assertRaises(requests.ConnectionError):
            api_client.get_employees()

    def test_timeout_propagates(self):
        self.mock_request.side_effect = (
            requests.Timeout("Request timed out")
        )
        with self.assertRaises(requests.Timeout):
            api_client.generate_recommendations()

if __name__ == "__main__":
    unittest.main()
