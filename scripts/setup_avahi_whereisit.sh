#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
AVAHI_CONF="/etc/avahi/avahi-daemon.conf"
DOCKER_NETWORK_NAME="whereisit_mdns"
DOCKER_BRIDGE_IFACE="br-whereisit"

log() { printf '[%s] %s\n' "$SCRIPT_NAME" "$*"; }
warn() { printf '[%s] WARN: %s\n' "$SCRIPT_NAME" "$*" >&2; }
die() { printf '[%s] ERROR: %s\n' "$SCRIPT_NAME" "$*" >&2; exit 1; }

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Please run as root, e.g. sudo bash $SCRIPT_NAME"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

install_avahi() {
  log "Installing Avahi..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y avahi-daemon avahi-utils
}

ensure_docker_bridge_network() {
  log "Ensuring docker network '${DOCKER_NETWORK_NAME}' with bridge iface '${DOCKER_BRIDGE_IFACE}'..."
  if docker network inspect "$DOCKER_NETWORK_NAME" >/dev/null 2>&1; then
    local iface
    iface="$(docker network inspect -f '{{ index .Options "com.docker.network.bridge.name" }}' "$DOCKER_NETWORK_NAME" 2>/dev/null || true)"
    if [[ "$iface" != "$DOCKER_BRIDGE_IFACE" ]]; then
      die "Network '$DOCKER_NETWORK_NAME' exists but bridge iface is '$iface' (expected '$DOCKER_BRIDGE_IFACE'). Please remove and recreate it."
    fi
    return
  fi

  docker network create \
    --driver bridge \
    --opt "com.docker.network.bridge.name=${DOCKER_BRIDGE_IFACE}" \
    "$DOCKER_NETWORK_NAME" >/dev/null
  log "Created docker network '$DOCKER_NETWORK_NAME'."
}

detect_uplink_iface() {
  local iface
  iface="$(ip -o route show default 2>/dev/null | awk '{print $5}' | head -n1 || true)"
  [[ -n "$iface" ]] || die "Cannot detect default uplink interface."
  printf '%s\n' "$iface"
}

write_avahi_config() {
  local uplink_iface="$1"
  local allow_interfaces="${uplink_iface},${DOCKER_BRIDGE_IFACE}"
  local backup_path=""

  if [[ -f "$AVAHI_CONF" ]]; then
    backup_path="${AVAHI_CONF}.bak.$(date +%Y%m%d%H%M%S)"
    cp -a "$AVAHI_CONF" "$backup_path"
    log "Backed up current config to $backup_path"
  fi

  cat >"$AVAHI_CONF" <<EOF
[server]
use-ipv4=yes
use-ipv6=no
allow-interfaces=${allow_interfaces}

[reflector]
enable-reflector=yes
EOF

  log "Wrote $AVAHI_CONF"
  log "allow-interfaces=${allow_interfaces}"
}

restart_avahi() {
  systemctl enable avahi-daemon >/dev/null
  systemctl restart avahi-daemon
  systemctl --no-pager --full status avahi-daemon | sed -n '1,12p'
}

main() {
  require_root
  require_cmd apt-get
  require_cmd ip
  require_cmd docker
  require_cmd systemctl

  install_avahi
  ensure_docker_bridge_network
  local uplink_iface
  uplink_iface="$(detect_uplink_iface)"
  write_avahi_config "$uplink_iface"
  restart_avahi

  log "Done. Next steps:"
  log "1) Ensure .env contains SERVICE_ADVERTISE_HOST=<your LAN IP>"
  log "2) Start app: docker compose -f docker-compose.avahi.yml up -d"
  log "3) Verify: avahi-browse -atr | grep -i whereisit"
}

main "$@"
