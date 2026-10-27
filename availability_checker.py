"""Low-rate, identifiable availability checks for an allowlisted target."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import requests


MAX_REQUESTS = 30
REQUEST_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 5
USER_AGENT = "AuthorizedAvailabilityCheck/1.0 (+https://github.com/davytheprogrammer/Website-Traffic-Generator-web-version)"


class AvailabilityChecker:
    """Run a bounded sequence of clearly identified GET checks against one URL."""

    def __init__(self, url, max_requests, session_id):
        self.url = url
        self.max_requests = min(int(max_requests), MAX_REQUESTS)
        self.session_id = session_id
        self.requests_completed = 0
        self.requests = []
        self.started_at = None
        self.finished_at = None
        self.error = None
        self._active = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def is_active(self):
        with self._lock:
            return self._active

    def stop(self):
        self._stop_event.set()

    def snapshot(self):
        with self._lock:
            completed = list(self.requests)
            active = self._active
            started_at = self.started_at
            finished_at = self.finished_at
            error = self.error
        elapsed = 0.0
        if started_at:
            end = datetime.now(timezone.utc) if active else finished_at
            if end:
                elapsed = max(0.0, (end - started_at).total_seconds())
        latencies = [item["duration_ms"] for item in completed if item["duration_ms"] is not None]
        statuses = [item["status_code"] for item in completed if item["status_code"] is not None]
        return {
            "session_id": self.session_id,
            "url": self.url,
            "active": active,
            "complete": bool(finished_at),
            "requests_completed": len(completed),
            "max_requests": self.max_requests,
            "elapsed_seconds": round(elapsed, 1),
            "average_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "success_count": sum(200 <= code < 300 for code in statuses),
            "error_count": sum(code >= 400 for code in statuses) + sum(item["error"] is not None for item in completed),
            "error": error,
            "user_agent": USER_AGENT,
            "requests": completed,
        }

    def start(self):
        with self._lock:
            if self._active:
                return
            self._active = True
            self.started_at = datetime.now(timezone.utc)
        try:
            while not self._stop_event.is_set() and self.requests_completed < self.max_requests:
                started = time.monotonic()
                item = {
                    "url": self.url,
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "status_code": None,
                    "duration_ms": None,
                    "error": None,
                    "redirect_blocked": False,
                }
                try:
                    # A single, clearly identified request. Do not follow redirects,
                    # impersonate browsers, persist cookies, or fetch page assets.
                    response = requests.get(
                        self.url,
                        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                        timeout=REQUEST_TIMEOUT_SECONDS,
                        allow_redirects=False,
                        stream=True,
                    )
                    item["status_code"] = response.status_code
                    item["redirect_blocked"] = 300 <= response.status_code < 400
                    response.close()
                    if response.status_code in {429, 503}:
                        with self._lock:
                            self.error = f"Target returned HTTP {response.status_code}; stopped early to reduce pressure on the service."
                        self._stop_event.set()
                except requests.RequestException as exc:
                    item["error"] = f"{type(exc).__name__}: {exc}"

                item["duration_ms"] = round((time.monotonic() - started) * 1000)
                with self._lock:
                    self.requests.append(item)
                    self.requests_completed += 1

                # Keep a full minimum gap even after a user stop or the final
                # request, so starting another session cannot bypass the rate cap.
                remaining = max(0.0, REQUEST_INTERVAL_SECONDS - (time.monotonic() - started))
                if remaining:
                    time.sleep(remaining)
        except Exception as exc:  # Keep a failed worker visible in its session status.
            with self._lock:
                self.error = f"{type(exc).__name__}: {exc}"
        finally:
            with self._lock:
                self._active = False
                self.finished_at = datetime.now(timezone.utc)
