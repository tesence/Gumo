FROM python:3.9-alpine

RUN apk --no-cache update && \
    apk --no-cache upgrade
RUN apk add --no-cache build-base

WORKDIR /app

COPY gumo ./gumo
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENTRYPOINT ["python", "-m", "gumo"]
