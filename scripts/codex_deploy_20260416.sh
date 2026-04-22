#!/usr/bin/env bash
set -euo pipefail

HOST='192.168.7.186'
USER='docker'
PASS='docker'
TAG='20260416'

run_remote() {
  sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$USER@$HOST" "$1"
}

run_remote "cd /opt/docker/whereisit && sed -i 's#demon3434/where_is_it:[0-9]\\{8\\}#demon3434/where_is_it:${TAG}#g' docker-compose.avahi.yml docker-compose.yml"
run_remote "cd /opt/docker/whereisit && grep -n 'demon3434/where_is_it' docker-compose.avahi.yml docker-compose.yml"
run_remote "cd /opt/docker/whereisit && docker compose -f docker-compose.avahi.yml pull app"
run_remote "cd /opt/docker/whereisit && docker compose -f docker-compose.avahi.yml up -d --force-recreate app"
run_remote "cd /opt/docker/whereisit && docker compose -f docker-compose.avahi.yml ps app --format json"
run_remote "curl -fsS http://127.0.0.1:3000/api/health"
