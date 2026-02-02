# Echo Processor - Production Image
# Process Class Spec v1.0 compliant

FROM python:3.12-alpine

WORKDIR /app

# Copy source
COPY src/main.py .

# Make executable
RUN chmod +x main.py

# Process reads from stdin, writes to stdout
# No CLI arguments required (spec compliance)
ENTRYPOINT ["python", "main.py"]
