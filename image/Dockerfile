FROM node:24-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6 AS node

FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS certificates
# Bootstrap TLS from an exact package in Ubuntu's signed archive.
RUN apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends ca-certificates=20240203

FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
ARG TARGETARCH
ARG WORKSPACE_RELEASE=0.3.0-preview1
ARG UBUNTU_SNAPSHOT=20260921T000000Z
LABEL org.opencontainers.image.title="HPC development workspace" \
      org.opencontainers.image.version="${WORKSPACE_RELEASE}" \
      org.opencontainers.image.description="Core Linux tools for Apptainer 1.3.6–1.5; GPU toolkits and site MPI are separate integrations."
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    WS_RELEASE=${WORKSPACE_RELEASE} \
    DISABLE_AUTOUPDATER=1 DISABLE_UPDATES=1 \
    PATH="/opt/workspace/bin:/opt/nvim/bin:/opt/workspace/node_modules/.bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
COPY --from=certificates /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
RUN test "${TARGETARCH:-amd64}" = amd64 \
    && printf 'APT::Snapshot "%s";\n' "$UBUNTU_SNAPSHOT" > /etc/apt/apt.conf.d/50snapshot \
    && apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends \
       bash bash-completion ca-certificates curl wget git openssh-client less file \
       rsync tar unzip xz-utils zstd zip procps htop lsof util-linux tzdata \
       ripgrep fd-find fzf bat jq tmux \
       python3 python3-venv python3-pip python3-dev python3-yaml \
       build-essential gfortran cmake ninja-build pkg-config gdb clangd \
       shellcheck shfmt \
    && mkdir -p /opt/workspace/bin /opt/workspace/manifests \
    && dpkg-query -W -f='${Package}\t${Version}\n' > /opt/workspace/manifests/apt-packages.tsv \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/fdfind /opt/workspace/bin/fd \
    && ln -s /usr/bin/batcat /opt/workspace/bin/bat
COPY --from=node /usr/local/ /usr/local/
WORKDIR /opt/workspace
COPY image/package.json image/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund \
    && npm cache clean --force \
    && node --version > manifests/node-version.txt \
    && npm ls --all --json > manifests/npm-packages.json
COPY image/assets.lock.json manifests/assets.lock.json
COPY scripts/install-assets.py /tmp/install-assets.py
RUN python3 /tmp/install-assets.py manifests/assets.lock.json /tmp/assets \
    && mv /tmp/assets/neovim /opt/nvim \
    && mkdir -p share \
    && mv /tmp/assets/tmux-* share/ \
    && rm -rf /tmp/assets /tmp/install-assets.py
COPY share/skills/ share/skills/
COPY share/skills.lock.json share/LICENSE-* share/
COPY image/config/ config/
COPY scripts/container-* bin/
COPY bin/ws bin/ws
COPY lib/*.py lib/
COPY profiles/ruth.json profiles/jean.json profiles/blueback.json profiles/
RUN chmod 0755 bin/container-* \
    && useradd --uid 10001 --create-home --shell /bin/bash workspace \
    && mkdir /workspace-state \
    && chown workspace:workspace /workspace-state \
    && printf '%s\n' "$WORKSPACE_RELEASE" > manifests/release.txt
USER workspace
WORKDIR /home/workspace
ENTRYPOINT ["/opt/workspace/bin/container-entry"]
