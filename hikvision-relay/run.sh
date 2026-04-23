#!/bin/sh
export LD_LIBRARY_PATH=/opt/hik-sdk:${LD_LIBRARY_PATH}
exec python3 /opt/relay_server.py
