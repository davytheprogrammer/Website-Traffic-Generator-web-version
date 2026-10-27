"""Local dashboard for bounded, authorized website availability checks."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request

from availability_checker import AvailabilityChecker, MAX_REQUESTS, REQUEST_INTERVAL_SECONDS
from url_validator import normalize_origin, validate_url


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        ALLOWED_ORIGINS={
            origin
            for value in os.environ.get("LOADTEST_ALLOWED_ORIGINS", "").split(",")
            if (origin := normalize_origin(value))
        },
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    app.active_sessions = {}
    app.sessions_lock = threading.Lock()

    def same_origin_request():
        origin = request.headers.get("Origin")
        if not origin:
            return False
        try:
            parsed = urlsplit(origin)
        except ValueError:
            return False
        return parsed.scheme == "http" and parsed.netloc.lower() == request.host.lower()

    def validate_target(raw_url):
        return validate_url(raw_url, app.config["ALLOWED_ORIGINS"])

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            allowed_origins=sorted(app.config["ALLOWED_ORIGINS"]),
            max_requests=MAX_REQUESTS,
            request_interval=REQUEST_INTERVAL_SECONDS,
            current_year=datetime.now(timezone.utc).year,
        )

    @app.post("/api/validate")
    def validate_url_endpoint():
        if not same_origin_request():
            return jsonify(valid=False, message="Cross-origin requests are not allowed."), 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(valid=False, message="Send a JSON object containing the target URL."), 400
        valid, message, normalized_url = validate_target(data.get("url"))
        return jsonify(valid=valid, message=message, url=normalized_url), 200 if valid else 400

    @app.post("/api/checks")
    def start_check():
        if not same_origin_request():
            return jsonify(success=False, message="Cross-origin requests are not allowed."), 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(success=False, message="Send a JSON object containing the check settings."), 400
        valid, message, normalized_url = validate_target(data.get("url"))
        if not valid:
            return jsonify(success=False, message=message), 400
        if data.get("authorized") is not True:
            return jsonify(success=False, message="Confirm that you own or are authorized to test this origin."), 400
        raw_requested = data.get("requests", 0)
        if isinstance(raw_requested, bool) or not str(raw_requested).isdigit():
            return jsonify(success=False, message="Request count must be a whole number."), 400
        requested = int(raw_requested)
        if not 1 <= requested <= MAX_REQUESTS:
            return jsonify(success=False, message=f"Choose between 1 and {MAX_REQUESTS} requests."), 400

        with app.sessions_lock:
            if any(item["thread"].is_alive() or item["checker"].is_active() for item in app.active_sessions.values()):
                return jsonify(success=False, message="A check is already running. Stop it before starting another."), 409
            # Keep the in-memory history bounded.
            finished = [key for key, item in app.active_sessions.items() if not item["thread"].is_alive()]
            while len(app.active_sessions) >= 10 and finished:
                app.active_sessions.pop(finished.pop(0), None)
            if len(app.active_sessions) >= 10:
                return jsonify(success=False, message="Session history is full. Restart the local app to clear it."), 409

            session_id = f"{int(time.time())}-{os.urandom(8).hex()}"
            checker = AvailabilityChecker(normalized_url, requested, session_id)
            thread = threading.Thread(target=checker.start, name=f"check-{session_id}", daemon=True)
            app.active_sessions[session_id] = {"checker": checker, "thread": thread}
            thread.start()

        return jsonify(success=True, session_id=session_id), 202

    @app.post("/api/checks/<session_id>/stop")
    def stop_check(session_id):
        if not same_origin_request():
            return jsonify(success=False, message="Cross-origin requests are not allowed."), 403
        item = app.active_sessions.get(session_id)
        if not item:
            return jsonify(success=False, message="Session not found."), 404
        item["checker"].stop()
        return jsonify(success=True)

    @app.get("/api/checks/<session_id>")
    def session_status(session_id):
        item = app.active_sessions.get(session_id)
        if not item:
            return jsonify(active=False, message="Session not found."), 404
        return jsonify(item["checker"].snapshot())

    return app


app = create_app()


if __name__ == "__main__":
    # Local-only by default. Do not expose this control panel to the public internet.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
