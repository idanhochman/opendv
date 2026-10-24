# Reference toolchain for opendv. Everything opendv is tested against lives here.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates build-essential autoconf flex bison help2man perl \
    python3 python3-venv python3-dev libfl2 libfl-dev zlib1g-dev liblz4-dev \
    ccache libgoogle-perftools-dev numactl lcov \
    && rm -rf /var/lib/apt/lists/*

ARG VERILATOR_TAG=v5.052
RUN git clone --depth 1 --branch ${VERILATOR_TAG} https://github.com/verilator/verilator /tmp/verilator \
    && cd /tmp/verilator && autoconf && ./configure --prefix=/opt/verilator \
    && make -j"$(nproc)" && make install && rm -rf /tmp/verilator
ENV PATH=/opt/verilator/bin:$PATH

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --retries 5 --default-timeout 100 -r /tmp/requirements.txt

COPY pyproject.toml README.md /opt/opendv/
COPY opendv /opt/opendv/opendv
RUN pip install --no-cache-dir --retries 5 --default-timeout 100 /opt/opendv
