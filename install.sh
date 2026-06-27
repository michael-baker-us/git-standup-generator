#!/usr/bin/env bash
# Git Standup Generator — installer
# Usage: bash install.sh [--ai] [--dev]
#
#   --ai   also install the anthropic package for AI-powered summaries
#   --dev  editable install (source changes take effect immediately)
#
# Re-running this script upgrades an existing installation.

set -euo pipefail

# ── colours ─────────────────────────────────────────────────────────────────
BOLD=$'\033[1m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[0;31m'
DIM=$'\033[2m'
NC=$'\033[0m'

step()    { printf "\n${BOLD}  →${NC}  %s\n" "$*"; }
ok()      { printf   "${GREEN}  ✓${NC}  %s\n" "$*"; }
warn()    { printf   "${YELLOW}  !${NC}  %s\n" "$*"; }
die()     { printf   "${RED}  ✗${NC}  %s\n" "$*" >&2; exit 1; }
detail()  { printf   "${DIM}     %s${NC}\n" "$*"; }

# ── paths ────────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.standup-generator"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"
BIN_PATH="$BIN_DIR/standup"

# ── flags ────────────────────────────────────────────────────────────────────
OPT_AI=false
OPT_DEV=false
for arg in "$@"; do
  case "$arg" in
    --ai)  OPT_AI=true  ;;
    --dev) OPT_DEV=true ;;
    *)     die "Unknown option: $arg  (supported: --ai, --dev)" ;;
  esac
done

# ── header ───────────────────────────────────────────────────────────────────
echo
echo "${BOLD}  Git Standup Generator${NC}"
echo "  ──────────────────────────────────────"
if $OPT_AI;  then detail "AI summaries enabled (--ai)";  fi
if $OPT_DEV; then detail "Editable install (--dev)"; fi

# ── prerequisites ────────────────────────────────────────────────────────────
step "Checking prerequisites"

# Python 3.11+
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" &>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
[[ -n "$PYTHON" ]] || die "Python not found. Install Python 3.11+ and retry."

PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")
PY_VERSION="$PY_MAJOR.$PY_MINOR"

if [[ "$PY_MAJOR" -lt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11 ) ]]; then
  die "Python 3.11+ required — found $PY_VERSION. Install a newer version and retry."
fi
ok "Python $PY_VERSION"

# git
command -v git &>/dev/null || die "git not found. Install git and retry."
GIT_VERSION=$(git --version | awk '{print $3}')
ok "git $GIT_VERSION"

# ── virtual environment ───────────────────────────────────────────────────────
step "Setting up virtual environment"
detail "Location: $VENV_DIR"

mkdir -p "$INSTALL_DIR"
if [[ -d "$VENV_DIR" ]]; then
  detail "Existing environment found — reusing"
else
  "$PYTHON" -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
"$PIP" install --quiet --upgrade pip
ok "Virtual environment ready"

# ── install package ───────────────────────────────────────────────────────────
step "Installing standup"

EXTRAS=""
if $OPT_AI; then EXTRAS="[ai]"; fi

if $OPT_DEV; then
  "$PIP" install --quiet -e "${REPO_DIR}${EXTRAS}"
  detail "Editable install — changes to source take effect immediately"
else
  "$PIP" install --quiet "${REPO_DIR}${EXTRAS}"
fi

VERSION=$("$VENV_DIR/bin/standup" --version 2>/dev/null || echo "unknown")
ok "Installed v$VERSION"

# ── wrapper script ────────────────────────────────────────────────────────────
step "Creating standup command"
detail "Location: $BIN_PATH"

mkdir -p "$BIN_DIR"
cat > "$BIN_PATH" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/standup" "\$@"
EOF
chmod +x "$BIN_PATH"
ok "Command created"

# ── PATH check ────────────────────────────────────────────────────────────────
if ! echo ":${PATH}:" | grep -q ":${BIN_DIR}:"; then
  step "Updating PATH"

  SHELL_NAME="$(basename "${SHELL:-bash}")"
  case "$SHELL_NAME" in
    zsh)  RC="$HOME/.zshrc" ;;
    bash) RC="${HOME}/.bash_profile"; [[ -f "$HOME/.bashrc" ]] && RC="$HOME/.bashrc" ;;
    fish) RC="$HOME/.config/fish/config.fish" ;;
    *)    RC="" ;;
  esac

  PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

  if [[ -n "$RC" ]]; then
    if grep -qF '.local/bin' "$RC" 2>/dev/null; then
      detail "$BIN_DIR already referenced in $RC"
    else
      printf '\n# Added by standup installer\n%s\n' "$PATH_LINE" >> "$RC"
      ok "Added $BIN_DIR to PATH in $RC"
      warn "Reload your shell or run:  source $RC"
    fi
  else
    warn "Add this to your shell config, then reload:"
    warn "  $PATH_LINE"
  fi
fi

# ── done ─────────────────────────────────────────────────────────────────────
echo
echo "  ${GREEN}${BOLD}Done.${NC}"
echo
echo "  Run ${BOLD}standup${NC} to launch the interactive UI."
echo
echo "  ${DIM}To use AI summaries later:     bash install.sh --ai${NC}"
echo "  ${DIM}To upgrade after a git pull:   bash install.sh${NC}"
echo "  ${DIM}To uninstall:                  rm -rf $INSTALL_DIR $BIN_PATH${NC}"
echo
