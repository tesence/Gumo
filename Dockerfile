FROM python:3.10-alpine

RUN apk --no-cache update && \
    apk --no-cache upgrade
RUN apk add --no-cache gcc musl-dev build-base git

WORKDIR /app

COPY gumo ./gumo
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENTRYPOINT ["python", "-m", "gumo"]
