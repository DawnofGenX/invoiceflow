#!/usr/bin/env bash
# InvoiceFlow — one-shot, idempotent VM setup.
#
# Installs Docker if missing, clones/updates the repo, builds and starts the
# stack, waits for the API to answer, seeds demo data on a fresh database, and
# prints the URL to verify.
#
#   ./scripts/vm_setup.sh                # install/update and (re)start the stack
#   ./scripts/vm_setup.sh --reset        # wipe the database volume first
#   ./scripts/vm_setup.sh --check        # report what is installed, change nothing
#
# Requirements: Debian/Ubuntu VM, sudo, outbound HTTPS, and a repo-root .env
# containing at least OPENCODE_API_KEY (see .env.example).

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/invoiceflow}"
REPO_URL="${REPO_URL:-https://github.com/DawnofGenX/invoiceflow.git}"
PORT="${PORT:-80}"
RESET=0
CHECK_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --reset) RESET=1 ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32mok\033[0m  %s\n' "$*"; }
warn() { printf '    \033[33mwarn\033[0m %s\n' "$*"; }
die()  { printf '\n    \033[31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

need_sudo() { if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi; }

# ---------------------------------------------------------------- 1. docker
say "1/6 Docker"
need_sudo
DOCKER_OK=1
command -v docker >/dev/null 2>&1 || DOCKER_OK=0
docker compose version >/dev/null 2>&1 || DOCKER_OK=0

if [ "$CHECK_ONLY" = "1" ]; then
  if [ "$DOCKER_OK" = "1" ]; then
    ok "docker $(docker --version | awk '{print $3}' | tr -d ,), compose $(docker compose version --short)"
  else
    warn "docker or the compose plugin is missing — run without --check to install"
  fi
elif [ "$DOCKER_OK" = "1" ]; then
  ok "already installed"
else
  echo "    installing docker-ce from download.docker.com"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq ca-certificates curl gnupg >/dev/null
  $SUDO install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
    $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
  $SUDO chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
    $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin >/dev/null
  $SUDO systemctl enable --now docker >/dev/null
  ok "installed $(docker --version)"
fi

if [ "$CHECK_ONLY" = "0" ] && ! docker info >/dev/null 2>&1; then
  echo "    adding $USER to the docker group"
  $SUDO usermod -aG docker "$USER"
  die "re-run this script (or 'newgrp docker') so the docker group applies"
fi

# ------------------------------------------------------------------ 2. repo
say "2/6 Repository at $APP_DIR"
if [ "$CHECK_ONLY" = "1" ]; then
  [ -d "$APP_DIR/.git" ] || die "$APP_DIR is not a git clone"
  ok "$(git -C "$APP_DIR" log --oneline -1)"
elif [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
  ok "cloned $REPO_URL"
else
  git -C "$APP_DIR" fetch --quiet origin
  git -C "$APP_DIR" merge --ff-only --quiet origin/main ||
    die "$APP_DIR has local changes that conflict with origin/main — resolve them first"
  ok "$(git -C "$APP_DIR" log --oneline -1)"
fi

# ------------------------------------------------------------------- 3. env
say "3/6 Environment file"
if [ -f "$APP_DIR/.env" ]; then
  # shellcheck disable=SC1091
  set -a; . "$APP_DIR/.env"; set +a
  [ -n "${OPENCODE_API_KEY:-}" ] || die ".env exists but OPENCODE_API_KEY is empty"
  ok "OPENCODE_API_KEY set (${#OPENCODE_API_KEY} chars), OPENCODE_SESSION=${OPENCODE_SESSION:-unset}"
elif [ "$CHECK_ONLY" = "1" ]; then
  warn "$APP_DIR/.env is missing"
else
  die "missing $APP_DIR/.env — copy .env.example to .env and fill OPENCODE_API_KEY"
fi

if [ "$CHECK_ONLY" = "1" ]; then
  say "4/6 Stack"; docker compose -f "$APP_DIR/docker-compose.yml" --project-directory "$APP_DIR" ps || true
  say "6/6 Summary"; ok "check complete — nothing was changed"
  exit 0
fi

# ------------------------------------------------------------------ 4. stack
say "4/6 Build and start"
cd "$APP_DIR"
if [ "$RESET" = "1" ]; then
  warn "--reset: removing containers and the database volume"
  docker compose down -v
fi
docker compose up -d --build
docker compose ps --format '{{.Name}} {{.Status}}' | sed 's/^/    /'

# ------------------------------------------------------------- 5. readiness
say "5/6 Waiting for the API"
for i in $(seq 1 45); do
  if curl -fsS -m 3 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    ok "healthy after $((i * 2))s: $(curl -fsS -m 3 "http://127.0.0.1:$PORT/api/health")"
    break
  fi
  sleep 2
  [ "$i" = "45" ] || continue
  docker compose logs --tail 40 backend | sed 's/^/    /'
  die "API did not become healthy in 90s — see the backend log above"
done

# ------------------------------------------------------------------ 6. seed
say "6/6 Demo data"
SEEDED=$(curl -fsS -m 10 -X POST "http://127.0.0.1:$PORT/api/seed/" || echo '{}')
echo "    $SEEDED"
curl -fsS -m 10 "http://127.0.0.1:$PORT/api/dashboard/" | sed 's/^/    /'
echo
BASE="http://127.0.0.1"; [ "$PORT" = "80" ] || BASE="http://127.0.0.1:$PORT"
printf '\033[1mDone.\033[0m The stack is running behind nginx on port %s.\n' "$PORT"
echo "    local check : curl -s $BASE/api/health"
echo "    public check: curl -s http://<vm-public-ip>${BASE#http://127.0.0.1}/api/health   (needs the NSG/firewall port open)"
echo "    full verify : python3 scripts/e2e_smoke.py --base-url http://<vm-public-ip>${BASE#http://127.0.0.1} --verbose"
