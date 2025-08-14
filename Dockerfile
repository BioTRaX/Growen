FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install .
COPY . .
EXPOSE 8000
CMD ["uvicorn", "services.api:app", "--host", "0.0.0.0", "--port", "8000"]
