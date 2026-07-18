FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
RUN mkdir -p /app/data /app/logs

RUN useradd -m -u 1000 amberuser && chown -R amberuser:amberuser /app
USER amberuser

CMD ["python", "-u", "src/amber_alert.py"]
