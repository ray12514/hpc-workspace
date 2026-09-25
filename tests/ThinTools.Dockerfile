# Fast editor iteration with public native Linux tools. Final acceptance still
# exercises the real SIF through Apptainer in thin-behavior.py.
ARG WORKSPACE_IMAGE=hpc-workspace-thin:0.7.1-preview1
ARG APPTAINER_IMAGE=hpc-workspace-apptainer:1.5.3
FROM ${APPTAINER_IMAGE} AS native
USER root
RUN apt-get update && apt-get install -y --no-install-recommends git python3-yaml \
    && rm -rf /var/lib/apt/lists/*
USER 1000:1000
FROM ${WORKSPACE_IMAGE}
USER root
COPY --from=native /usr/ /usr/
COPY --from=native /etc/ /etc/
RUN ["/workspace-tools/libexec/python3", "-I", "-c", "import os; os.symlink('usr/lib','/lib'); os.symlink('usr/lib64','/lib64'); os.unlink('/bin/bash'); os.symlink('/usr/bin/bash','/bin/bash'); os.unlink('/bin/sh'); os.symlink('/usr/bin/sh','/bin/sh')"]
USER 10001:10001
