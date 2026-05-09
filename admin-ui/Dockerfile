FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py /app/
COPY templates /app/templates
COPY static /app/static

EXPOSE 8080
CMD ["python", "-u", "app.py"]
