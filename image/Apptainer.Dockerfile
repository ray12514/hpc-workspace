FROM node:24-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6
ARG APPTAINER_VERSION=1.5.3
ARG APPTAINER_SHA256=82b0bdddf459087d202383360b8318d526ad6826c748a2f669913cc6aef9ee40
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl --fail --location --retry 3 \
       "https://github.com/apptainer/apptainer/releases/download/v${APPTAINER_VERSION}/apptainer_${APPTAINER_VERSION}_amd64.deb" \
       --output /tmp/apptainer.deb \
    && printf '%s  /tmp/apptainer.deb\n' "$APPTAINER_SHA256" | sha256sum --check \
    && apt-get install -y --no-install-recommends /tmp/apptainer.deb \
    && rm -rf /var/lib/apt/lists/* /tmp/apptainer.deb \
    && apptainer version
ENTRYPOINT ["apptainer"]
