FROM python:3.11-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir fastapi>=0.110.0 uvicorn>=0.27.0 pydantic>=2.7.0
COPY . /srv
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
