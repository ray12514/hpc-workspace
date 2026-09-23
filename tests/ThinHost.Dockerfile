# Public Ubuntu host fixture with the same Apptainer as the Debian fixture.
FROM hpc-workspace-apptainer:1.5.3 AS runtime
FROM hpc-workspace:0.4.0-preview1
USER root
COPY --from=runtime /usr/bin/apptainer /usr/bin/apptainer
COPY --from=runtime /usr/libexec/apptainer/ /usr/libexec/apptainer/
COPY --from=runtime /etc/apptainer/ /etc/apptainer/
COPY --from=runtime /lib/x86_64-linux-gnu/liblzo2.so.2* /lib/x86_64-linux-gnu/
COPY --from=runtime /var/lib/apptainer/ /var/lib/apptainer/
RUN apptainer version
USER workspace
ENTRYPOINT []
