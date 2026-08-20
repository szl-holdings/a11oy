"""Locust workload with receipt-integrity validation."""

import os
import uuid

from locust import HttpUser, between, task


class GDWUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def step(self):
        request_id = "locust-" + uuid.uuid4().hex
        session_id = (
            os.environ.get("GDW_LOCUST_SHARED_SESSION")
            or "locust-" + uuid.uuid4().hex
        )
        token = os.environ.get("GDW_BENCH_TOKEN", "")
        with self.client.post(
            "/api/a11oy/v1/gdw/step",
            json={
                "session_id": session_id,
                "request": "high-concurrency validation request",
                "allowed_experts": ["planner", "retriever", "auditor"],
                "risk_budget": 0.35,
                "mode_hint": "auto",
                "dry_run": False,
            },
            headers={
                "Authorization": "Bearer " + token,
                "X-Request-Id": request_id,
            },
            name="gdw_step",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            try:
                body = response.json()
            except Exception:
                response.failure("malformed JSON")
                return
            if body.get("decision") == "ACCEPT" and not body.get("receipt_hash"):
                response.failure("accepted transition omitted receipt_hash")
