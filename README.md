# Echo Processor

A simple echo processor for testing ProcessMonitor system.

## Purpose

This is a minimal Process Class implementation following the [Process Class Specification v1.0](../../../docs/process-class-specification-v1.md).

It echoes back the input message with simulated processing steps.

## Input

```json
{
  "message": "Hello, World!",
  "delay": 1,
  "shouldFail": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | Yes | - | Message to echo back |
| `delay` | integer | No | 1 | Delay in seconds between steps (0-10) |
| `shouldFail` | boolean | No | false | If true, process fails with error |

## Output

```json
{
  "echoedMessage": "ECHO: Hello, World!",
  "processedAt": "2026-02-02T10:30:00.123456+00:00",
  "executionId": "abc-123"
}
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | Info | Debug, Info, Warning, Error |
| `EXECUTION_ID` | No | unknown | Unique execution identifier |

## Build & Run

```bash
# Build
docker build -t echo-processor:latest .

# Run
echo '{"message":"Hello"}' | docker run -i \
  -v /tmp/logs:/logs \
  -e LOG_LEVEL=Info \
  -e EXECUTION_ID=test-001 \
  echo-processor:latest

# Run tests
docker build -f Dockerfile.test -t echo-processor:test .
docker run echo-processor:test
```

## Example Session

```bash
$ echo '{"message":"Test message","delay":0}' | docker run -i \
    -v /tmp/logs:/logs \
    echo-processor:latest

{"type": "progress", "percent": 0, "message": "Starting..."}
{"type": "progress", "percent": 10, "message": "Input validated"}
{"type": "progress", "percent": 25, "message": "Processing input..."}
{"type": "progress", "percent": 50, "message": "Transforming data..."}
{"type": "progress", "percent": 75, "message": "Preparing output..."}
{"type": "progress", "percent": 90, "message": "Finalizing..."}
{"type": "progress", "percent": 100, "message": "Done"}
{"type": "result", "data": {"echoedMessage": "ECHO: Test message", "processedAt": "2026-02-02T10:30:00.123456+00:00", "executionId": "unknown"}}

$ echo $?
0
```

## Error Handling

With `shouldFail: true`:

```bash
$ echo '{"message":"Test","shouldFail":true}' | docker run -i echo-processor:latest

{"type": "progress", "percent": 0, "message": "Starting..."}
{"type": "progress", "percent": 10, "message": "Input validated"}
{"type": "progress", "percent": 50, "message": "Processing..."}
{"type": "error", "code": "SIMULATED_FAILURE", "message": "Process failed as requested by shouldFail=true"}

$ echo $?
1
```
