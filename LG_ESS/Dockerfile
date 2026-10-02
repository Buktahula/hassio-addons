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
    && find /usr/local/lib -name "essmqtt.py" -exec sed -i "s/from distutils.util import strtobool/from setuptools._distutils.util import strtobool/" {} + 2>/dev/null || true

COPY data/run.sh /
COPY data/lgess_mqtt.py /usr/share/lgess_mqtt.py
RUN chmod +x /run.sh /usr/share/lgess_mqtt.py

CMD [ "/run.sh" ]
