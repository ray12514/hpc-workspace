FROM nixos/nix:2.34.1@sha256:1d59121e0c361076b4f23c158d236702f2f045b3b477b51075b81ceb6188d34a AS tools
ARG WORKSPACE_RELEASE=0.5.1-preview1
COPY image/nix/ /build/nix/
RUN nix --extra-experimental-features 'nix-command flakes' build \
      --no-write-lock-file --out-link /build/toolbox /build/nix \
    && mkdir -p /output/nix/store /output/workspace-tools /output/bin /output/etc /output/tmp /output/home/workspace \
    && nix-store --query --requisites /build/toolbox > /build/closure \
    && while read -r path; do cp -a "$path" /output/nix/store/; done < /build/closure \
    && cp -a /build/toolbox/. /output/workspace-tools/ \
    && printf '%s\n' "$WORKSPACE_RELEASE" > /output/workspace-tools/manifests/release.txt \
    && cp /build/closure /output/workspace-tools/manifests/closure.txt \
    && cp /build/nix/flake.lock /output/workspace-tools/manifests/flake.lock \
    && ln -s /workspace-tools/bin/bash /output/bin/sh \
    && ln -s /workspace-tools/bin/bash /output/bin/bash \
    && printf 'root:x:0:0:root:/root:/bin/bash\nworkspace:x:10001:10001:Workspace:/home/workspace:/bin/bash\n' > /output/etc/passwd \
    && printf 'root:x:0:\nworkspace:x:10001:\n' > /output/etc/group \
    && chmod 1777 /output/tmp && chmod 0777 /output/home/workspace

RUN mv /output/workspace-tools/bin/tmux /output/workspace-tools/libexec/tmux \
    && ln -s /workspace-tools/thin-tmux /output/workspace-tools/bin/tmux

FROM scratch
ARG WORKSPACE_RELEASE=0.5.1-preview1
ARG WORKSPACE_REVISION=development
LABEL org.opencontainers.image.title="Integrated HPC development environment" \
      org.opencontainers.image.version="${WORKSPACE_RELEASE}" \
      org.opencontainers.image.revision="${WORKSPACE_REVISION}" \
      org.hpc-workspace.layout="thin-v1"
COPY --from=tools /output/ /
COPY image/config/ /workspace-tools/config/
COPY share/tmux-resurrect/ /workspace-tools/share/tmux-resurrect/
COPY share/tmux-continuum/ /workspace-tools/share/tmux-continuum/
COPY share/skills/ /workspace-tools/share/skills/
COPY share/skills.lock.json share/LICENSE-* /workspace-tools/share/
COPY scripts/thin-entry scripts/thin-shell scripts/thin-session scripts/thin-nvim scripts/thin-tmux /workspace-tools/
COPY lib/*.py /workspace-tools/lib/
COPY profiles/ruth.json profiles/jean.json profiles/blueback.json /workspace-tools/profiles/
COPY bin/ws /workspace-tools/bin/ws
ENV PATH="/workspace-tools/bin:/usr/local/bin:/usr/bin:/bin" \
    HOME=/home/workspace LANG=C.UTF-8 WS_LAYOUT=thin-v1 WS_RELEASE=${WORKSPACE_RELEASE}
USER 10001:10001
WORKDIR /home/workspace
ENTRYPOINT ["/workspace-tools/thin-entry"]
