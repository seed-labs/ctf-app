FROM i386/ubuntu:trusty AS build

RUN apt update && apt install -y \
    ed \
    g++ \
    csh \
    make \
    netcat \
    && rm -rf /var/lib/apt/lists/*

LABEL maintainer="tthoma17@syr.edu>"

ADD bof_vulnerable_server.c .

ARG ddummy_size=1000

ARG dbuf_size=500

RUN echo DBUF_SIZE=${dbuf_size} DDUMMY_SIZE=${ddummy_size} && gcc -static -DBUF_SIZE=${dbuf_size} -DDUMMY_SIZE=${ddummy_size} bof_vulnerable_server.c -o bof_vulnerable_server -z execstack -fno-stack-protector

ARG bof_secret=randomsecret

RUN echo ${bof_secret} > ./pasfile

FROM i386/ubuntu:trusty

COPY --from=build bof_vulnerable_server .

COPY --from=build pasfile /tmp/

EXPOSE 9090

ENTRYPOINT ["/bof_vulnerable_server", "-l 1", "-p 9090", "-b 127.0.0.1"]