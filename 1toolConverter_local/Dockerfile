
<<<<<<< HEAD
FROM python:3.14.0
=======
FROM python:3.11-slim
>>>>>>> 982801cc65734a6870ff04d57845a1ab6e1413c0

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app


COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 8080

CMD ["python", "main.py"]