#!/bin/bash
set -euo pipefail

cp /tmp/suricata.yaml /etc/suricata/suricata.yaml
mkdir -p /var/lib/suricata/rules
cp /tmp/suricata.rules /var/lib/suricata/rules/suricata.rules
mkdir -p /var/log/suricata

# Docker may create this path as a directory when the file does not exist yet.
# Suricata needs eve.json to be a regular file so the UI and monitor can read it.
if [ -d /var/log/suricata/eve.json ]; then
  rm -rf /var/log/suricata/eve.json
fi
touch /var/log/suricata/eve.json

exec suricata -c /etc/suricata/suricata.yaml --af-packet
