FROM python:3.8-slim

RUN apt-get update \
    && apt-get install -y git \
    && apt-get clean

WORKDIR /app
COPY requirements.txt /app
RUN pip install -U pip \
    && pip install -r requirements.txt \
    && pip install git+https://github.com/tweepy/tweepy.git \
    && rm -rf ~/.cache/pip

COPY . /app

CMD ["python", "main.py"]
