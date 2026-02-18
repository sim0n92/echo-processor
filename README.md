# Echo Processor

A simple echo processor for testing ProcessMonitor system.

## Purpose

This is a minimal Process Class implementation following the [Process Class Specification v1.0](../../../docs/process-class-specification-v1.md) with the actions protocol.

It echoes back the input message with simulated processing steps, and supports graceful termination.

## Actions

### Execute

Echoes back the input message with simulated processing.

**Input:**

```json
{
  "_action": "execute",
  "_meta": { "executionId": "abc-123" },
  "message": "Hello, World!",
  "delay": 1,
  "shouldFail": false,
  "minRunSeconds": 0
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | Yes | - | Message to echo back |
| `delay` | integer | No | 1 | Delay in seconds between steps (0-10) |
| `shouldFail` | boolean | No | false | If true, process fails with error |
| `minRunSeconds` | integer | No | 0 | Minimum run time in seconds (0-300), useful for testing terminate |

**Output:**

```json
{
  "echoedMessage": "ECHO v2.0: !DLROW ,OLLEH",
  "processedAt": "2026-02-02T10:30:00.123456+00:00",
  "executionId": "abc-123"
}
```

### Terminate

Gracefully terminates a running execution. Can be sent as:
- **Initial action** (first stdin message): immediately returns `{"cleaned": true}` and exits
- **Subsequent message** during an execute: signals the running handler to stop, which emits a `TERMINATED` error and exits with code 3

**Input:**

```json
{
  "_action": "terminate",
  "_meta": { "executionId": "abc-123" }
}
```

**Output (when sent as initial action):**

```json
{
  "type": "result",
  "data": { "cleaned": true }
}
```

## Protocol Fields

All stdin messages use the actions protocol:

| Field | Description |
|-------|-------------|
| `_action` | Action to perform: `execute` or `terminate` |
| `_meta.executionId` | Execution identifier (overrides `EXECUTION_ID` env var) |
| `_meta.callbackBaseUrl` | Optional callback URL (reserved for future use) |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | Info | Debug, Info, Warning, Error |
| `EXECUTION_ID` | No | unknown | Unique execution identifier (overridden by `_meta.executionId`) |

## Build & Run

```bash
# Build
docker build -t echo-processor:latest .

# Run execute action
echo '{"_action":"execute","_meta":{"executionId":"test-001"},"message":"Hello"}' | docker run -i \
  -v /tmp/logs:/logs \
  -e LOG_LEVEL=Info \
  echo-processor:latest

# Run terminate action
echo '{"_action":"terminate","_meta":{"executionId":"test-001"}}' | docker run -i \
  -v /tmp/logs:/logs \
  echo-processor:latest

# Run tests
docker build -f Dockerfile.test -t echo-processor:test .
docker run echo-processor:test
```

## Example Session

### Execute action

```bash
$ echo '{"_action":"execute","_meta":{"executionId":"test-1"},"message":"Test message","delay":0}' | docker run -i \
    -v /tmp/logs:/logs \
    echo-processor:latest

{"type": "progress", "percent": 0, "message": "Starting..."}
{"type": "progress", "percent": 10, "message": "Input validated"}
{"type": "progress", "percent": 25, "message": "Processing input..."}
{"type": "progress", "percent": 50, "message": "Transforming data..."}
{"type": "progress", "percent": 75, "message": "Preparing output..."}
{"type": "progress", "percent": 90, "message": "Finalizing..."}
{"type": "progress", "percent": 100, "message": "Done"}
{"type": "result", "data": {"echoedMessage": "ECHO v2.0: EGASSEM TSET", "processedAt": "2026-02-02T10:30:00.123456+00:00", "executionId": "test-1"}}

$ echo $?
0
```

### Terminate action (initial)

```bash
$ echo '{"_action":"terminate","_meta":{"executionId":"test-1"}}' | docker run -i \
    -v /tmp/logs:/logs \
    echo-processor:latest

{"type": "progress", "percent": 0, "message": "Starting..."}
{"type": "progress", "percent": 10, "message": "Input validated"}
{"type": "result", "data": {"cleaned": true}}

$ echo $?
0
```

### Missing _action field

```bash
$ echo '{"message":"Hello"}' | docker run -i echo-processor:latest

{"type": "progress", "percent": 0, "message": "Starting..."}
{"type": "error", "code": "MISSING_ACTION", "message": "Required field '_action' is missing from input"}

$ echo $?
2
```

## Error Handling

With `shouldFail: true`:

```bash
$ echo '{"_action":"execute","_meta":{"executionId":"test-1"},"message":"Test","shouldFail":true}' | docker run -i echo-processor:latest

{"type": "progress", "percent": 0, "message": "Starting..."}
{"type": "progress", "percent": 10, "message": "Input validated"}
{"type": "progress", "percent": 50, "message": "Processing..."}
{"type": "error", "code": "SIMULATED_FAILURE", "message": "Process failed as requested by shouldFail=true"}

$ echo $?
1
```
