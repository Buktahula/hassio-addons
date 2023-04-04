ARG BUILD_FROM
FROM $BUILD_FROM

# Build PYESS 
ARG PYESS_VERSION
WORKDIR /usr/share
RUN \
    apk add --no-cache --virtual .build-dependencies \
        build-base \
        py3-pip \
        python3 \   
     && pip install pyess
COPY essmqtt.config /etc/essmqtt.config
COPY essmqtt.service /etc/systemd/system/essmqtt.service

WORKDIR /usr/share
