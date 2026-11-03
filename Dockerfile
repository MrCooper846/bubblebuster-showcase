FROM python:3.12-slim
WORKDIR /case
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "demo"]
