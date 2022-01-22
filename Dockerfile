FROM python:3.9-slim

RUN apt-get update \
    && apt-get install -y git \
    && apt-get clean

WORKDIR /app
COPY requirements.txt /app
RUN pip install -U pip \
    && pip install -r requirements.txt \
    && rm -rf ~/.cache/pip

COPY . /app

CMD ["python", "main.py"]
