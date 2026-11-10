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
