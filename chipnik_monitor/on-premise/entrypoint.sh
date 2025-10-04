#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "[$(date --iso-8601=seconds)] $*"
}

start_noip() {
  if [[ -z "${NOIP_USERNAME:-}" || -z "${NOIP_PASSWORD:-}" ]]; then
    log "No-IP credentials not provided; skipping dynamic DNS startup"
    return 1
  fi

  local cmd=(/usr/local/bin/noip-duc)

  if [[ -n "${NOIP_ARGS:-}" ]]; then
    # shellcheck disable=SC2206
    cmd+=(${NOIP_ARGS})
  fi

  log "Starting No-IP dynamic DNS client"
  "${cmd[@]}" &
  NOIP_PID=$!
  return 0
}

start_noip || true

: "${GH_RUNNER_URL:?GH_RUNNER_URL must be set}"
: "${GH_RUNNER_TOKEN:?GH_RUNNER_TOKEN must be set}"

RUNNER_NAME="${GH_RUNNER_NAME:-${HOSTNAME}}"
RUNNER_WORKDIR="${GH_RUNNER_WORKDIR:-_work}"
RUNNER_LABELS="${GH_RUNNER_LABELS:-}"

cleanup() {
  log "Shutting down runner"
  if [[ -f "config.sh" ]]; then
    ./config.sh remove --token "${GH_RUNNER_TOKEN}" || true
  fi
  if [[ -n "${NOIP_PID:-}" ]]; then
    log "Stopping No-IP client"
    kill "${NOIP_PID}" 2>/dev/null || true
    wait "${NOIP_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ -f .runner ]]; then
  log "Removing stale runner configuration"
  ./config.sh remove --token "${GH_RUNNER_TOKEN}" || true
  rm -f .runner
fi

CONFIG_ARGS=(--unattended --url "${GH_RUNNER_URL}" --token "${GH_RUNNER_TOKEN}" --name "${RUNNER_NAME}" --work "${RUNNER_WORKDIR}")
if [[ "${GH_RUNNER_REPLACE:-}" == "true" ]]; then
  CONFIG_ARGS+=(--replace)
fi
if [[ "${GH_RUNNER_EPHEMERAL:-}" == "true" ]]; then
  CONFIG_ARGS+=(--ephemeral)
fi
if [[ -n "${RUNNER_LABELS}" ]]; then
  CONFIG_ARGS+=(--labels "${RUNNER_LABELS}")
fi

log "Configuring GitHub Actions runner"
./config.sh "${CONFIG_ARGS[@]}"

log "Starting GitHub Actions runner"
exec ./run.sh "$@"