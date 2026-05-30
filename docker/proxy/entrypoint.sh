#!/bin/sh
set -e

# Write the single allowed host from ALLOW_HOST env var
ALLOW_HOST="${ALLOW_HOST:-api.anthropic.com}"
echo "${ALLOW_HOST}" > /etc/tinyproxy/allow.txt

# Write tinyproxy config (deny-by-default, Spec B)
cat > /etc/tinyproxy/tinyproxy.conf << EOF
Port 8888
Listen 0.0.0.0
Timeout 600
MaxClients 10
MinSpareServers 1
MaxSpareServers 3
StartServers 2
MaxRequestsPerChild 0
LogLevel Error
# Deny everything not in the filter list
FilterDefaultDeny Yes
# Only allow HTTPS CONNECT (port 443)
ConnectPort 443
# The filter file contains exactly one hostname
Filter "/etc/tinyproxy/allow.txt"
EOF

echo "tinyproxy: allowing CONNECT to ${ALLOW_HOST}:443 only"
exec tinyproxy -d -c /etc/tinyproxy/tinyproxy.conf
