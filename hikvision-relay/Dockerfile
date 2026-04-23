ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

# Install Python3 (libuuid.so.1 is bundled in sdk/ directory)
RUN apk add --no-cache python3

# Copy Hikvision SDK for the right architecture
ARG BUILD_ARCH=aarch64
COPY sdk/${BUILD_ARCH}/ /opt/hik-sdk/

# Copy application
COPY relay_server.py run.sh /opt/
RUN chmod +x /opt/run.sh

CMD ["/opt/run.sh"]
