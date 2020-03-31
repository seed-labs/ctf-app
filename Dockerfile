FROM python:3.7-alpine3.10

RUN apk update \
  && apk add \
    build-base \
    postgresql \
    postgresql-dev \
    libpq \
    nodejs \
    npm \
    docker \
    mysql-client \
    py-mysqldb \
    mariadb-dev

RUN mkdir /usr/src/app

WORKDIR /usr/src/app

COPY ./requirements.txt .

RUN pip install mysqlclient

RUN pip install -r requirements.txt

ENV PYTHONUNBUFFERED 1

COPY . .

ENV API_HOST localhost

ENV API_PORT 5000

RUN npm install && npm run build 

COPY src/assets/. build/src/assets/.