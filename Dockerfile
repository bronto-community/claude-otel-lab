FROM python:3.13-slim
WORKDIR /lab
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY oncall ./oncall
COPY scripts ./scripts
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "oncall.app:app", "--host", "0.0.0.0", "--port", "8000"]
