import json
import statistics
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"

def benchmark(endpoint, method="GET", payload=None, runs=20):
    times = []
    failures = 0

    print(f"\nTesting {method} {endpoint}...")

    for _ in range(runs):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None

        request = urllib.request.Request(
            BASE_URL + endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )

        start = time.perf_counter()

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                response.read()

            times.append((time.perf_counter() - start) * 1000)

        except urllib.error.HTTPError as error:
            failures += 1
            print(f"HTTP {error.code}: {error.read().decode()}")

        except Exception as error:
            failures += 1
            print(f"Request failed: {error}")

    print(f"Successful requests: {len(times)}/{runs}")
    print(f"Failed requests: {failures}")

    if times:
        print(f"Average: {statistics.mean(times):.2f} ms")
        print(f"Median:  {statistics.median(times):.2f} ms")
        print(f"Maximum: {max(times):.2f} ms")


# Basic API endpoints
benchmark("/employees")
benchmark("/tasks")
benchmark("/workloads")

# AI-related validation
benchmark(
    "/recommendations/evaluate",
    method="POST",
    payload={
        "selected_recommendations": [
            {"task_id": 6, 
             "employee_id": 1,
             "reason": "Benchmark test."}
        ]
    },
)

# Actual Gemini generation: only three requests
benchmark(
    "/recommendations",
    method="POST",
    runs=3,
)
