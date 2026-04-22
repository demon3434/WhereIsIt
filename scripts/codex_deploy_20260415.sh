#!/usr/bin/env bash
set -euo pipefail

HOST='192.168.7.186'
USER='docker'
PASS='docker'

run_remote() {
  sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$USER@$HOST" "$1"
}

run_remote "cd /opt/docker/whereisit && sed -i 's#demon3434/where_is_it:latest#demon3434/where_is_it:20260415#g' docker-compose.avahi.yml docker-compose.yml"
run_remote "cd /opt/docker/whereisit && grep -n 'demon3434/where_is_it' docker-compose.avahi.yml docker-compose.yml"
run_remote "cd /opt/docker/whereisit && docker compose -f docker-compose.avahi.yml pull app"
run_remote "cd /opt/docker/whereisit && docker compose -f docker-compose.avahi.yml up -d app"
run_remote "cd /opt/docker/whereisit && docker compose -f docker-compose.avahi.yml ps app"
run_remote "cd /opt/docker/whereisit && WEB_PORT=\$(awk -F= '/^WEB_PORT=/{print \$2}' .env | tail -n1); curl -fsS http://127.0.0.1:\${WEB_PORT}/api/health"