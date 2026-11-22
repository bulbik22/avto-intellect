FROM python:3.12-slim
WORKDIR /app/backend
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services ./services
CMD ["uvicorn", "services.users.main:app", "--host", "0.0.0.0", "--port", "8000"]
