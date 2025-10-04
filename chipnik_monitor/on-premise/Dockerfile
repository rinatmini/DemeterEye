FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG RUNNER_VERSION=2.319.1

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tar \
    jq \
    unzip \
    git \
    build-essential \
    libicu70 \
    libssl3 \
    lsb-release \
    gdal-bin \
    libgdal-dev \
    proj-bin \
    libproj-dev \
  && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://www.noip.com/download/linux/latest -o /tmp/noip-duc.tar.gz \
  && tar -xzf /tmp/noip-duc.tar.gz -C /tmp \
  && NOIP_ARCHIVE="$(find /tmp -name 'noip-duc_*_x86_64-musl.gz' -print -quit)" \
  && [[ -n "${NOIP_ARCHIVE}" ]] \
  && gunzip "${NOIP_ARCHIVE}" \
  && mv "${NOIP_ARCHIVE::-3}" /usr/local/bin/noip-duc \
  && chmod +x /usr/local/bin/noip-duc \
  && rm -rf /tmp/noip-duc.tar.gz /tmp/noip-duc_*

RUN useradd -m --uid 1000 runner \
  && mkdir -p /actions-runner \
  && chown runner:runner /actions-runner

WORKDIR /actions-runner

RUN curl -fsSL -o actions-runner.tar.gz https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz \
  && tar -xzf actions-runner.tar.gz \
  && rm actions-runner.tar.gz \
  && ./bin/installdependencies.sh \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
  && chown runner:runner /entrypoint.sh

USER runner

ENTRYPOINT ["/entrypoint.sh"]

