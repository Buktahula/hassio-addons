ARG BUILD_FROM
FROM $BUILD_FROM

# Build PYESS 
ARG PYESS_VERSION
WORKDIR /usr/src
RUN \
    apk add --no-cache --virtual .build-dependencies \
        build-base \
        py3-pip \
        python3 \   
     && pip install pyess
WORKDIR /
