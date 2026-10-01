ARG BUILD_FROM
FROM $BUILD_FROM

# Install PYESS and clean up build dependencies
ARG PYESS_VERSION
WORKDIR /usr/share

RUN \
    apk add --no-cache --virtual .build-dependencies \
        build-base \
        python3-dev \
    && pip install --no-cache-dir pyess setuptools \
    && apk del --no-network .build-dependencies \
    && find /usr/local/lib -name "essmqtt.py" -exec sed -i "s/from distutils.util import strtobool/from setuptools._distutils.util import strtobool/" {} +

COPY data/run.sh /
RUN chmod +x /run.sh

CMD [ "/run.sh" ]
