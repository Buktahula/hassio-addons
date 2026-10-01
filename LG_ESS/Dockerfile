ARG BUILD_FROM
FROM $BUILD_FROM

# Install PYESS and clean up build dependencies
ARG PYESS_VERSION
WORKDIR /usr/share

RUN \
    apk add --no-cache --virtual .build-dependencies \
        build-base \
        python3-dev \
    && pip install --no-cache-dir pyess \
    && apk del --no-network .build-dependencies

COPY data/run.sh /
RUN chmod +x /run.sh

CMD [ "/run.sh" ]
