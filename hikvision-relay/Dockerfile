ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-debian:latest
FROM ${BUILD_FROM}

# Install Python3 (Debian/glibc base — required by Hikvision SDK binaries)
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*

# Copy Hikvision SDK for the right architecture
ARG BUILD_ARCH=aarch64
COPY sdk/${BUILD_ARCH}/ /opt/hik-sdk/

# Copy application
COPY relay_server.py run.sh /opt/
RUN chmod +x /opt/run.sh

CMD ["/opt/run.sh"]
