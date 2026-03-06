#!/bin/bash
# Auto-configure netkitx CLI from environment variables

mkdir -p /root/.netkitx

API="${NETKITX_API:-http://127.0.0.1:8000}"
TOKEN="${NETKITX_TOKEN:-}"

cat > /root/.netkitx/config.json << EOF
{
  "api": "${API}",
  "token": "${TOKEN}"
}
EOF

echo "NetKitX Sandbox"
echo "API: ${API}"
if [ -n "${TOKEN}" ]; then
    echo "Status: authenticated"
else
    echo "Status: run 'netkitx login -u USER -p PASS' to authenticate"
fi
echo "---"

exec "$@"
