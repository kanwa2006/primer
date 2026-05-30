# PRIMER egress proxy image (Spec B)
# Deny-by-default tinyproxy sidecar.
# Allows CONNECT to exactly one host:443 (the agent's API host).
# The ALLOW_HOST env var is set by network.py at container start.

FROM alpine:3.18

RUN apk add --no-cache tinyproxy

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8888

ENTRYPOINT ["/entrypoint.sh"]
