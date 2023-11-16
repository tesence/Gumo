FROM python:3.11.6-alpine

WORKDIR /app

COPY gumo ./gumo
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENTRYPOINT ["python", "-m", "gumo"]
