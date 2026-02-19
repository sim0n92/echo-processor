#!/usr/bin/env python3
"""
Echo Processor - Sample Process Class (stdin type)

Follows Process Class Specification v1.0 (actions protocol):
- Reads JSON Lines from stdin (first line = action message)
- Routes to execute or terminate based on _action field
- Emits progress/result/error on stdout (JSON Lines)
- Reports progress to ProcessMonitor via authenticated callback endpoint
- Obtains Bearer token via OAuth2 client credentials (Keycloak)
- Writes diagnostic logs to /logs/events.log
- Respects LOG_LEVEL environment variable
- Supports graceful termination via stdin terminate message
"""

import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# Log levels
LOG_LEVELS = {"Debug": 0, "Info": 1, "Warning": 2, "Error": 3}

# Thread-safe termination signal
_terminate_event = threading.Event()


class Logger:
    """Simple logger that writes to /logs/events.log"""

    def __init__(self):
        self.level = LOG_LEVELS.get(os.environ.get("LOG_LEVEL", "Info"), 1)
        self.log_path = Path("/logs/events.log")

        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open log file in append mode
        self.log_file = open(self.log_path, "a", encoding="utf-8")

    def _log(self, level_name: str, level_num: int, message: str, data: dict = None):
        if level_num >= self.level:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            abbrev = {"Debug": "DBG", "Info": "INF", "Warning": "WRN", "Error": "ERR"}[level_name]

            line = f"{timestamp} [{abbrev}] {message}"
            if data:
                line += f" {json.dumps(data)}"

            self.log_file.write(line + "\n")
            self.log_file.flush()

    def debug(self, message: str, data: dict = None):
        self._log("Debug", 0, message, data)

    def info(self, message: str, data: dict = None):
        self._log("Info", 1, message, data)

    def warning(self, message: str, data: dict = None):
        self._log("Warning", 2, message, data)

    def error(self, message: str, data: dict = None):
        self._log("Error", 3, message, data)

    def close(self):
        self.log_file.close()


class CallbackClient:
    """HTTP client for reporting progress to ProcessMonitor via callback endpoint.

    Uses OAuth2 client credentials flow (Keycloak) for authentication.
    All methods are no-ops if callback_base_url or keycloak config is missing,
    allowing graceful degradation for local testing.
    """

    def __init__(self, callback_base_url: str | None, execution_id: str,
                 keycloak_config: dict | None, logger):
        self.callback_base_url = callback_base_url
        self.execution_id = execution_id
        self.keycloak = keycloak_config
        self.logger = logger
        self._cached_token: str | None = None
        self.enabled = bool(callback_base_url and keycloak_config
                            and keycloak_config.get("tokenUrl")
                            and keycloak_config.get("clientId")
                            and keycloak_config.get("clientSecret"))

    def _get_token(self) -> str | None:
        """Obtain Bearer token via OAuth2 client credentials grant."""
        if self._cached_token:
            return self._cached_token

        try:
            data = urllib.parse.urlencode({
                "grant_type": "client_credentials",
                "client_id": self.keycloak["clientId"],
                "client_secret": self.keycloak["clientSecret"],
            }).encode("utf-8")

            req = urllib.request.Request(
                self.keycloak["tokenUrl"],
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                self._cached_token = body["access_token"]
                self.logger.info("Keycloak token obtained successfully")
                return self._cached_token

        except Exception as e:
            self.logger.warning("Failed to obtain Keycloak token", {"error": str(e)})
            return None

    def report_progress(self, percent: int, message: str):
        """POST progress to {callbackBaseUrl}/executions/{executionId}/progress.

        Logs warnings on failure but never raises.
        """
        if not self.enabled:
            return

        token = self._get_token()
        if not token:
            return

        url = f"{self.callback_base_url}/executions/{self.execution_id}/progress"
        payload = json.dumps({"percent": percent, "message": message}).encode("utf-8")

        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.logger.debug("Progress callback sent", {"percent": percent, "status": resp.status})
        except Exception as e:
            self.logger.warning("Progress callback failed", {"percent": percent, "error": str(e)})


def emit(message: dict):
    """Emit a JSON message to stdout (JSON Lines format)"""
    print(json.dumps(message, ensure_ascii=False), flush=True)


def emit_progress(percent: int | None, message: str):
    """Emit progress message"""
    emit({"type": "progress", "percent": percent, "message": message})


def emit_result(data: dict):
    """Emit result message (success)"""
    emit({"type": "result", "data": data})


def emit_error(code: str, message: str, data: dict = None):
    """Emit error message (managed failure)"""
    error_msg = {"type": "error", "code": code, "message": message}
    if data:
        error_msg["data"] = data
    emit(error_msg)


def extract_user_params(msg: dict) -> dict:
    """Strip _-prefixed protocol fields from input, returning only user params."""
    return {k: v for k, v in msg.items() if not k.startswith("_")}


def stdin_reader(logger):
    """Daemon thread: reads subsequent stdin lines after first message.

    Sets _terminate_event when a terminate action is received.
    """
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                action = msg.get("_action")
                if action == "terminate":
                    logger.info("Received terminate action via stdin")
                    _terminate_event.set()
                    return
                else:
                    logger.debug("Ignoring non-terminate stdin message", {"action": action})
            except json.JSONDecodeError:
                logger.warning("Invalid JSON on stdin (ignored)", {"line": line[:200]})
    except Exception as e:
        logger.error("stdin_reader error", {"error": str(e)})


def handle_execute(params: dict, execution_id: str, callback_client: CallbackClient, logger) -> int:
    """Execute the echo processing logic.

    Checks _terminate_event between steps for responsive termination.
    Uses _terminate_event.wait(timeout=...) instead of time.sleep().
    Reports progress to ProcessMonitor via callback_client.
    """
    start_time = time.monotonic()

    message = params.get("message")
    delay = params.get("delay", 1)
    should_fail = params.get("shouldFail", False)
    min_run_seconds = params.get("minRunSeconds", 0)

    if not message:
        logger.error("Missing required field: message")
        emit_error("MISSING_FIELD", "Required field 'message' is missing")
        return 2

    callback_client.report_progress(10, "Input validated")

    # Check if we should simulate failure
    if should_fail:
        logger.warning("Simulating failure as requested")
        emit_progress(50, "Processing...")
        _terminate_event.wait(timeout=delay)
        if _terminate_event.is_set():
            logger.info("Terminated during simulated failure")
            emit_error("TERMINATED", "Process was terminated")
            return 3
        emit_error("SIMULATED_FAILURE", "Process failed as requested by shouldFail=true")
        return 1

    # Simulate processing with progress
    steps = [
        (25, "Processing input..."),
        (50, "Transforming data..."),
        (75, "Preparing output..."),
        (90, "Finalizing..."),
    ]

    for percent, step_msg in steps:
        if _terminate_event.is_set():
            logger.info("Terminated during processing", {"atPercent": percent})
            emit_error("TERMINATED", "Process was terminated")
            return 3

        emit_progress(percent, step_msg)
        if percent == 50:
            callback_client.report_progress(50, "Transforming data...")
        logger.debug(f"Progress: {percent}%", {"step": step_msg})
        _terminate_event.wait(timeout=delay / len(steps))

    if _terminate_event.is_set():
        logger.info("Terminated after processing steps")
        emit_error("TERMINATED", "Process was terminated")
        return 3

    emit_progress(100, "Done")
    callback_client.report_progress(90, "Finalizing...")

    # Build result
    result = {
        "echoedMessage": f"ECHO v2.1: {message.upper()[::-1]}",
        "processedAt": datetime.now(timezone.utc).isoformat(),
        "executionId": execution_id,
    }

    # If minRunSeconds is set, wait until minimum time has elapsed
    if min_run_seconds > 0:
        elapsed = time.monotonic() - start_time
        remaining = min_run_seconds - elapsed
        while remaining > 0:
            if _terminate_event.is_set():
                logger.info("Terminated during minRunSeconds wait")
                emit_error("TERMINATED", "Process was terminated")
                return 3
            wait_time = min(1.0, remaining)
            _terminate_event.wait(timeout=wait_time)
            elapsed = time.monotonic() - start_time
            remaining = min_run_seconds - elapsed

    if _terminate_event.is_set():
        logger.info("Terminated after minRunSeconds wait")
        emit_error("TERMINATED", "Process was terminated")
        return 3

    logger.info("Processing completed successfully", {"result": result})
    emit_result(result)

    return 0


def handle_terminate(callback_client: CallbackClient, logger) -> int:
    """Handle a direct terminate action (first message is terminate)."""
    logger.info("Handling terminate action")
    emit_result({"cleaned": True})
    return 0


def main():
    logger = Logger()

    try:
        # Get execution ID from environment (may be overridden by _meta)
        execution_id = os.environ.get("EXECUTION_ID", "unknown")

        logger.info("Starting echo-processor", {"executionId": execution_id})
        emit_progress(0, "Starting...")

        # Read first JSON Line from stdin (keeps stdin open for subsequent messages)
        logger.debug("Reading first line from stdin")
        first_line = sys.stdin.readline()

        if not first_line.strip():
            logger.error("Empty input received")
            emit_error("EMPTY_INPUT", "No input provided on stdin")
            return 2

        try:
            msg = json.loads(first_line)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON input", {"error": str(e)})
            emit_error("INVALID_JSON", f"Input is not valid JSON: {e}")
            return 2

        logger.info("Input parsed successfully", {"msg": msg})

        # Extract protocol fields
        action = msg.get("_action")
        meta = msg.get("_meta", {})

        # _meta.executionId overrides env var
        if meta.get("executionId"):
            execution_id = meta["executionId"]
            logger.info("Execution ID overridden by _meta", {"executionId": execution_id})

        # Extract callback and keycloak config
        callback_base_url = meta.get("callbackBaseUrl")
        keycloak_config = meta.get("keycloak")

        if keycloak_config:
            # Log presence but NEVER log clientSecret
            logger.info("Keycloak config present", {
                "tokenUrl": keycloak_config.get("tokenUrl"),
                "clientId": keycloak_config.get("clientId"),
            })

        callback_client = CallbackClient(callback_base_url, execution_id, keycloak_config, logger)

        if callback_client.enabled:
            logger.info("Callback client enabled", {"callbackBaseUrl": callback_base_url})
        else:
            logger.debug("Callback client disabled (missing callbackBaseUrl or keycloak config)")

        if not action:
            logger.error("Missing _action field")
            emit_error("MISSING_ACTION", "Required field '_action' is missing from input")
            return 2

        # Extract user params (strip protocol fields)
        params = extract_user_params(msg)

        emit_progress(10, "Input validated")

        # Route to action handler
        if action == "execute":
            # Start stdin reader daemon thread for terminate signals
            reader_thread = threading.Thread(target=stdin_reader, args=(logger,), daemon=True)
            reader_thread.start()

            return handle_execute(params, execution_id, callback_client, logger)

        elif action == "terminate":
            return handle_terminate(callback_client, logger)

        else:
            logger.error("Unknown action", {"action": action})
            emit_error("UNKNOWN_ACTION", f"Unknown _action: {action}")
            return 2

    except Exception as e:
        logger.error("Unhandled exception", {"error": str(e), "type": type(e).__name__})
        # Don't emit error for unhandled exceptions - let stderr capture it
        raise

    finally:
        logger.close()


if __name__ == "__main__":
    sys.exit(main())
