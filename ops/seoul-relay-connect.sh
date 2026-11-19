#!/usr/bin/env bash
# No shell access or public reverse port. Verify host key independently before use.
set -euo pipefail
: "${RELAY_HOST:?Set the approved Seoul instance IP}"
: "${RELAY_KEY:?Set the dedicated private-key path}"
: "${RELAY_KNOWN_HOSTS:?Set the verified known-hosts file path}"
exec /usr/bin/ssh -NT \
    -o BatchMode=yes -o IdentitiesOnly=yes \
    -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$RELAY_KNOWN_HOSTS" \
    -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    -i "$RELAY_KEY" -R 127.0.0.1:18443:127.0.0.1:8443 "sushitunnel@$RELAY_HOST"
