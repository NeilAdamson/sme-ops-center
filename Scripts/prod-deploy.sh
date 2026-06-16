#!/usr/bin/env bash
#
# prod-deploy.sh — SME Ops-Center Docker deploy (production)
#
# Rebuilds, restarts, or stops the Docker Compose stack on a production host.
# This script does NOT provision Google Cloud resources — run GC-Build.ps1 (or
# equivalent IaC) separately before first deploy.
#
# ================================================================================
# QUICK START
# ================================================================================
#
# PREREQUISITES:
#   1. Docker Engine with Docker Compose v2+
#   2. Configured .env (or injected secrets via your secret manager)
#   3. GCP credentials mounted per docker-compose.yml / prod overrides
#
# COMMON COMMANDS:
#   # Pull, rebuild, and start detached (production default)
#   ./Scripts/prod-deploy.sh
#
#   # Full rebuild without cache
#   ./Scripts/prod-deploy.sh --action rebuild --no-cache
#
#   # Restart API gateway only
#   ./Scripts/prod-deploy.sh --action restart --services api-gateway
#
#   # Graceful stop (keeps volumes)
#   ./Scripts/prod-deploy.sh --action down
#
#   # Stop and remove named volumes (destructive — resets DB/cache)
#   ./Scripts/prod-deploy.sh --action down --remove-volumes
#
# ================================================================================

set -euo pipefail

ACTION="up"
SERVICES=()
DETACH=true
BUILD=true
NO_CACHE=false
PULL=true
REMOVE_VOLUMES=false
REMOVE_ORPHANS=true
FOLLOW=false
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME=""
PROJECT_ROOT=""

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Options:
  --action <up|down|restart|rebuild|stop|logs|ps>   Deploy action (default: up)
  --services <svc1,svc2,...>                        Limit to specific services
  --detach | --no-detach                            Run in background (default: detach)
  --build | --no-build                              Build images on up (default: build)
  --no-cache                                        Build without layer cache
  --pull | --no-pull                                Pull base images (default: pull on up/rebuild)
  --remove-volumes                                  Remove named volumes on down
  --remove-orphans | --no-remove-orphans            Prune orphan containers (default: remove)
  --follow                                          Follow logs (logs action)
  --compose-file <path>                             Compose file (default: docker-compose.yml)
  --project-name <name>                             Docker Compose project name
  --project-root <path>                             Repository root (default: parent of Scripts/)
  -h, --help                                        Show this help
EOF
}

log() {
  printf '\n==> %s\n' "$1"
}

run_cmd() {
  local description="$1"
  shift
  log "$description"
  printf '    %s\n' "$*"
  "$@"
}

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --action) ACTION="${2,,}"; shift 2 ;;
    --services)
      IFS=',' read -r -a SERVICES <<< "$2"
      shift 2
      ;;
    --detach) DETACH=true; shift ;;
    --no-detach) DETACH=false; shift ;;
    --build) BUILD=true; shift ;;
    --no-build) BUILD=false; shift ;;
    --no-cache) NO_CACHE=true; shift ;;
    --pull) PULL=true; shift ;;
    --no-pull) PULL=false; shift ;;
    --remove-volumes) REMOVE_VOLUMES=true; shift ;;
    --remove-orphans) REMOVE_ORPHANS=true; shift ;;
    --no-remove-orphans) REMOVE_ORPHANS=false; shift ;;
    --follow) FOLLOW=true; shift ;;
    --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
    --project-name) PROJECT_NAME="$2"; shift 2 ;;
    --project-root) PROJECT_ROOT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1 (use --help)" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "$PROJECT_ROOT" ]]; then
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
fi

if [[ "$COMPOSE_FILE" = /* ]]; then
  COMPOSE_FILE_PATH="$COMPOSE_FILE"
else
  COMPOSE_FILE_PATH="$PROJECT_ROOT/$COMPOSE_FILE"
fi

compose() {
  local description="$1"
  shift
  local -a cmd=(docker compose)
  if [[ -n "$PROJECT_NAME" ]]; then
    cmd+=(-p "$PROJECT_NAME")
  fi
  cmd+=(-f "$COMPOSE_FILE_PATH")
  cmd+=("$@")
  run_cmd "$description" "${cmd[@]}"
}

get_env_value() {
  local key="$1"
  local default="${2:-}"
  local env_file="$PROJECT_ROOT/.env"
  local line value

  if [[ ! -f "$env_file" ]]; then
    printf '%s' "$default"
    return
  fi

  line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$env_file" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' "$default"
    return
  fi

  value="${line#*=}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

summary_line() {
  printf '  %-22s %s\n' "$1" "$2"
}

show_quickstart_summary() {
  local environment_label="${1:-production}"
  local pg_user pg_password pg_db gcp_project gcs_bucket storage_backend data_store_id engine_id

  pg_user="$(get_env_value POSTGRES_USER smeops)"
  pg_password="$(get_env_value POSTGRES_PASSWORD change-me)"
  pg_db="$(get_env_value POSTGRES_DB smeops)"
  gcp_project="$(get_env_value GOOGLE_CLOUD_PROJECT '(not set in .env)')"
  gcs_bucket="$(get_env_value GCS_BUCKET_NAME '(not set in .env)')"
  storage_backend="$(get_env_value STORAGE_BACKEND local)"
  data_store_id="$(get_env_value DATA_STORE_ID '(not set)')"
  engine_id="$(get_env_value ENGINE_ID '(not set)')"

  printf '\n================================================================================\n'
  printf ' QUICKSTART - SME Ops-Center (%s)\n' "$environment_label"
  printf '================================================================================\n'

  printf '\nWeb URLs\n'
  summary_line "Frontend (Streamlit)" "http://localhost:8501"
  summary_line "API Gateway" "http://localhost:8000"
  summary_line "API docs (Swagger)" "http://localhost:8000/docs"
  summary_line "MCP Bridge" "http://localhost:3000"
  summary_line "Xero OAuth callback" "http://localhost:3000/oauth/xero/callback"

  printf '\nHealth & verification\n'
  summary_line "API health" "http://localhost:8000/health"
  summary_line "MCP health" "http://localhost:3000/health"
  summary_line "GCS smoke test" "http://localhost:8000/gcs/smoke"
  summary_line "Docs status API" "http://localhost:8000/docs/status"

  printf '\nExposed ports\n'
  summary_line "frontend" "8501"
  summary_line "api-gateway" "8000"
  summary_line "mcp-bridge" "3000"
  summary_line "postgres" "5432"
  summary_line "redis" "6379"

  printf '\nContainers\n'
  summary_line "frontend" "sme-frontend"
  summary_line "api-gateway" "sme-api-gateway"
  summary_line "worker" "sme-worker"
  summary_line "mcp-bridge" "sme-mcp-bridge"
  summary_line "postgres" "sme-postgres"
  summary_line "redis" "sme-redis"

  printf '\nDatabase (Postgres)\n'
  summary_line "Host" "localhost:5432"
  summary_line "Database" "$pg_db"
  summary_line "User" "$pg_user"
  summary_line "Password" "$pg_password"
  summary_line "Connect" "psql -h localhost -U $pg_user -d $pg_db"
  if [[ "$pg_password" == "change-me" ]]; then
    printf '  WARNING: Postgres still uses the default password - change POSTGRES_PASSWORD in .env and docker-compose.yml.\n'
  fi

  printf '\nApp auth\n'
  summary_line "UI / API login" "Not enabled yet (Sprint 3 security baseline)"

  printf '\nConfig (.env)\n'
  summary_line "Storage backend" "$storage_backend"
  summary_line "GCP project" "$gcp_project"
  summary_line "GCS bucket" "$gcs_bucket"
  summary_line "Data store ID" "$data_store_id"
  summary_line "Engine ID" "$engine_id"

  printf '\nUseful commands\n'
  summary_line "Container status" "./Scripts/prod-deploy.sh --action ps"
  summary_line "Follow logs" "./Scripts/prod-deploy.sh --action logs --follow"
  summary_line "Restart API" "./Scripts/prod-deploy.sh --action restart --services api-gateway"
  summary_line "Stop stack" "./Scripts/prod-deploy.sh --action down"
  summary_line "GCS smoke" "curl http://localhost:8000/gcs/smoke"

  printf '\nFirst checks\n'
  printf '  1. Open http://localhost:8501 - Docs module should load\n'
  printf '  2. Hit http://localhost:8000/health - expect healthy JSON\n'
  printf '  3. Hit http://localhost:8000/gcs/smoke - confirms GCP credentials and bucket access\n'
  printf '================================================================================\n\n'
}

preflight() {
  log "Preflight checks"
  command -v docker >/dev/null 2>&1 || die "docker CLI not found on PATH"
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required"
  [[ -f "$COMPOSE_FILE_PATH" ]] || die "Compose file not found: $COMPOSE_FILE_PATH"

  if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
    printf '  WARNING: .env not found at %s/.env\n' "$PROJECT_ROOT" >&2
  fi
}

preflight

case "$ACTION" in
  up)
    args=(up)
    [[ "$BUILD" == true ]] && args+=(--build)
    [[ "$DETACH" == true ]] && args+=(-d)
    [[ "$REMOVE_ORPHANS" == true ]] && args+=(--remove-orphans)
    [[ "$PULL" == true ]] && args+=(--pull always)
    args+=("${SERVICES[@]}")
    compose "Start production stack" "${args[@]}"
    ;;

  rebuild)
    build_args=(build)
    [[ "$NO_CACHE" == true ]] && build_args+=(--no-cache)
    [[ "$PULL" == true ]] && build_args+=(--pull)
    build_args+=("${SERVICES[@]}")
    compose "Rebuild images" "${build_args[@]}"

    up_args=(up -d)
    [[ "$REMOVE_ORPHANS" == true ]] && up_args+=(--remove-orphans)
    up_args+=("${SERVICES[@]}")
    compose "Start rebuilt stack (detached)" "${up_args[@]}"
    ;;

  restart)
    compose "Restart services" restart "${SERVICES[@]}"
    ;;

  stop)
    compose "Stop services" stop "${SERVICES[@]}"
    ;;

  down)
    down_args=(down)
    [[ "$REMOVE_VOLUMES" == true ]] && down_args+=(-v)
    [[ "$REMOVE_ORPHANS" == true ]] && down_args+=(--remove-orphans)
    compose "Stop and remove containers" "${down_args[@]}"
    ;;

  logs)
    log_args=(logs)
    [[ "$FOLLOW" == true ]] && log_args+=(-f)
    log_args+=("${SERVICES[@]}")
    compose "Show service logs" "${log_args[@]}"
    ;;

  ps)
    compose "List running services" ps
    ;;

  *)
    die "Unsupported action: $ACTION"
    ;;
esac

printf '\n==> Done (%s)\n' "$ACTION"
if [[ "$ACTION" == "up" || "$ACTION" == "rebuild" ]]; then
  show_quickstart_summary "production"
fi
