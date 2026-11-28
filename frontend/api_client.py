"""Shared HTTP client for the TaskFlow AI FastAPI backend."""

import os

import requests

API_BASE_URL = os.getenv("TASKFLOW_API_URL", "http://127.0.0.1:8000").rstrip("/")

def api_request(method, endpoint, data=None):
    """Call a FastAPI endpoint and return its decoded JSON response.

    Raises requests.RequestException for connection, timeout, or HTTP errors.
    """
    response = requests.request(
        method,
        f"{API_BASE_URL}{endpoint}",
        json=data,
        timeout=60 if endpoint == "/recommendations" else 10,
    )
    response.raise_for_status()
    return response.json()

def get_error_message(error):
    """Return a safe, user-friendly message for an API error."""

    if isinstance(error, requests.exceptions.Timeout):
        return "The request timed out. Please try again."

    if isinstance(error, requests.exceptions.ConnectionError):
        return "Could not connect to the backend. Ensure the application is running."

    if isinstance(error, requests.exceptions.HTTPError):
        response = error.response

        if response is not None:
            status = response.status_code

            if status == 400:
                return "The request could not be completed. Check the submitted information."

            if status == 404:
                return "The requested record could not be found."

            if status == 409:
                return "The data has changed. Refresh and try again."

            if status == 422:
                return "Invalid input. Check the submitted values and try again."

            if status == 502:
                return "The AI service could not provide a valid response. Please try again."

            if status == 503:
                try:
                    detail = response.json().get("detail")
                except (ValueError, AttributeError):
                    detail = None

                if detail == "Gemini API key is not configured.":
                    return "The Gemini API key is not configured."

                return "A required service is currently unavailable."

            if status >= 500:
                return "An internal service error occurred. Please try again."

    return "An unexpected error occurred. Please try again."

# Employee endpoints
def get_employees():
    return api_request("GET", "/employees")

def get_employee(employee_id):
    return api_request("GET", f"/employees/{employee_id}")

def create_employee(data):
    return api_request("POST", "/employees", data)

def update_employee(employee_id, data):
    return api_request("PUT", f"/employees/{employee_id}", data)

# Task endpoints
def get_tasks():
    return api_request("GET", "/tasks")

def get_task(task_id):
    return api_request("GET", f"/tasks/{task_id}")

def create_task(data):
    return api_request("POST", "/tasks", data)

def update_task(task_id, data):
    return api_request("PUT", f"/tasks/{task_id}", data)

# Workload endpoints
def get_workloads():
    return api_request("GET", "/workloads")

def get_employee_workload(employee_id):
    return api_request("GET", f"/employees/{employee_id}/workload")

# AI recommendation endpoints
def generate_recommendations():
    return api_request("POST", "/recommendations")

def preview_recommendation(data):
    return api_request("POST", "/recommendations/preview", data)

def evaluate_recommendations(data):
    return api_request("POST", "/recommendations/evaluate", data)

def approve_recommendations(data):
    return api_request("POST", "/recommendations/approve", data)
