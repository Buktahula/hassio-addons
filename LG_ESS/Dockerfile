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
COPY data/run.sh /
RUN ["chmod", "+x", "/run.sh"]
CMD [ "/run.sh" ]
