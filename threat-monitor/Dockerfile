FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy threat monitor script
COPY threat_monitor.py /app/

# Run threat monitor with unbuffered output
CMD ["python", "-u", "threat_monitor.py"]
