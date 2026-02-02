#!/usr/bin/env python3
"""
Echo Processor - Sample Process Class (stdin type)

Follows Process Class Specification v1.0:
- Reads JSON from stdin
- Emits progress/result/error on stdout (JSON Lines)
- Writes diagnostic logs to /logs/events.log
- Respects LOG_LEVEL environment variable
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# Log levels
LOG_LEVELS = {"Debug": 0, "Info": 1, "Warning": 2, "Error": 3}


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


def main():
    logger = Logger()

    try:
        # Get execution ID from environment
        execution_id = os.environ.get("EXECUTION_ID", "unknown")

        logger.info("Starting echo-processor", {"executionId": execution_id})
        emit_progress(0, "Starting...")

        # Read JSON from stdin
        logger.debug("Reading input from stdin")
        input_data = sys.stdin.read()

        if not input_data.strip():
            logger.error("Empty input received")
            emit_error("EMPTY_INPUT", "No input provided on stdin")
            return 2

        try:
            params = json.loads(input_data)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON input", {"error": str(e)})
            emit_error("INVALID_JSON", f"Input is not valid JSON: {e}")
            return 2

        logger.info("Input parsed successfully", {"params": params})
        emit_progress(10, "Input validated")

        # Extract parameters
        message = params.get("message")
        delay = params.get("delay", 1)
        should_fail = params.get("shouldFail", False)

        if not message:
            logger.error("Missing required field: message")
            emit_error("MISSING_FIELD", "Required field 'message' is missing")
            return 2

        # Check if we should simulate failure
        if should_fail:
            logger.warning("Simulating failure as requested")
            emit_progress(50, "Processing...")
            time.sleep(delay)
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
            emit_progress(percent, step_msg)
            logger.debug(f"Progress: {percent}%", {"step": step_msg})
            time.sleep(delay / len(steps))

        emit_progress(100, "Done")

        # Build result
        result = {
            "echoedMessage": f"ECHO: {message}",
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "executionId": execution_id
        }

        logger.info("Processing completed successfully", {"result": result})
        emit_result(result)

        return 0

    except Exception as e:
        logger.error("Unhandled exception", {"error": str(e), "type": type(e).__name__})
        # Don't emit error for unhandled exceptions - let stderr capture it
        raise

    finally:
        logger.close()


if __name__ == "__main__":
    sys.exit(main())
