FROM python:3.9-slim

RUN apt-get update \
    && apt-get install -y git \
    && apt-get clean

WORKDIR /app
COPY requirements.txt /app
RUN pip install -U pip \
    && pip install -r requirements.txt \
    && rm -rf ~/.cache/pip

COPY src/ /app/

# force the stdout and stderr streams to be unbuffered
ENV PYTHONUNBUFFERED=1

ENTRYPOINT [ "python", "main.py" ]
CMD [ "run" ]
