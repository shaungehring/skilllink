#!/usr/bin/env bash
# skilllink installer — install directly from GitHub
# Usage: curl -fsSL https://raw.githubusercontent.com/shaungehring/skilllink/main/install.sh | bash

set -euo pipefail

REPO="https://github.com/shaungehring/skilllink"
GITHUB_RAW="git+${REPO}.git"
GITHUB_RAW_BASE="https://raw.githubusercontent.com/shaungehring/skilllink/main"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10

# ---- Colors ----------------------------------------------------------------
if [ -t 1 ]; then
  BOLD="\033[1m"
  GREEN="\033[0;32m"
  YELLOW="\033[0;33m"
  RED="\033[0;31m"
  RESET="\033[0m"
else
  BOLD="" GREEN="" YELLOW="" RED="" RESET=""
fi

info()    { echo -e "${BOLD}${GREEN}==>${RESET} $*"; }
warn()    { echo -e "${YELLOW}Warning:${RESET} $*"; }
error()   { echo -e "${RED}Error:${RESET} $*" >&2; }
section() { echo -e "\n${BOLD}$*${RESET}"; }

# ---- OS check --------------------------------------------------------------
OS="$(uname -s)"
if [[ "$OS" == "MINGW"* || "$OS" == "CYGWIN"* || "$OS" == "MSYS"* ]]; then
  error "Windows is not supported by this installer."
  error "On Windows, install manually:"
  error "  pip install git+${REPO}.git"
  exit 1
fi

# ---- Python check ----------------------------------------------------------
section "Checking Python..."

PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" &>/dev/null; then
    version=$("$candidate" -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>/dev/null || true)
    major=$(echo "$version" | cut -d' ' -f1)
    minor=$(echo "$version" | cut -d' ' -f2)
    if [[ "$major" -ge "$MIN_PYTHON_MAJOR" && "$minor" -ge "$MIN_PYTHON_MINOR" ]]; then
      PYTHON="$candidate"
      info "Found $("$PYTHON" --version)"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  error "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ is required but not found."
  error "Install Python from https://python.org/downloads/ and re-run this script."
  exit 1
fi

# ---- pip check -------------------------------------------------------------
section "Checking pip..."

PIP=""
if "$PYTHON" -m pip --version &>/dev/null 2>&1; then
  PIP="$PYTHON -m pip"
elif command -v pip3 &>/dev/null; then
  PIP="pip3"
elif command -v pip &>/dev/null; then
  PIP="pip"
fi

if [ -z "$PIP" ]; then
  error "pip not found. Install pip and re-run:"
  error "  $PYTHON -m ensurepip --upgrade"
  exit 1
fi

info "Found pip: $($PIP --version | head -1)"

# ---- Install ---------------------------------------------------------------
section "Installing skilllink from GitHub..."

USER_INSTALL=false
PIPX_INSTALL=false

# Prefer pipx for CLI tools — it manages its own venv and avoids PEP 668 issues
if command -v pipx &>/dev/null; then
  info "Found pipx — using it for installation."
  if pipx install "$GITHUB_RAW"; then
    PIPX_INSTALL=true
  else
    warn "pipx install failed, falling back to pip..."
  fi
fi

if ! $PIPX_INSTALL; then
  if $PIP install "$GITHUB_RAW" 2>/dev/null; then
    : # success (system pip, no externally-managed restriction)
  elif $PIP install --user --break-system-packages "$GITHUB_RAW" 2>/dev/null; then
    USER_INSTALL=true
  elif $PIP install --user "$GITHUB_RAW" 2>/dev/null; then
    USER_INSTALL=true
  else
    error "Installation failed."
    error ""
    error "Your Python environment is externally managed (PEP 668)."
    error "The recommended fix is to install via pipx:"
    error ""
    error "  brew install pipx"
    error "  pipx install git+${REPO}.git"
    error ""
    error "Or install into a virtual environment manually:"
    error "  python3 -m venv ~/.skilllink-venv"
    error "  ~/.skilllink-venv/bin/pip install git+${REPO}.git"
    error "  ln -sf ~/.skilllink-venv/bin/skilllink /usr/local/bin/skilllink"
    exit 1
  fi
fi

# ---- PATH fix (user install or missing skilllink) --------------------------
section "Checking PATH..."

# Determine the user bin dir pip would have installed to
USER_BIN="$($PYTHON -m site --user-base 2>/dev/null)/bin"
SHELL_RC=""

# Detect the user's shell config file based on their login shell ($SHELL),
# not the current interpreter — this script is often run via "curl | bash"
# even on systems where the user's login shell is zsh.
case "$(basename "${SHELL:-}")" in
  zsh)  SHELL_RC="$HOME/.zshrc" ;;
  bash) SHELL_RC="$HOME/.bashrc"
        [ -f "$HOME/.bash_profile" ] && SHELL_RC="$HOME/.bash_profile" ;;
  *)
    # Fall back to running-interpreter detection
    if [ -n "${ZSH_VERSION:-}" ]; then
      SHELL_RC="$HOME/.zshrc"
    elif [ -n "${BASH_VERSION:-}" ]; then
      SHELL_RC="$HOME/.bashrc"
      [ -f "$HOME/.bash_profile" ] && SHELL_RC="$HOME/.bash_profile"
    fi
    ;;
esac

add_to_path() {
  local dir="$1"
  local export_line="export PATH=\"${dir}:\$PATH\""

  if [ -z "$SHELL_RC" ]; then
    warn "Could not detect shell config file. Add this to your shell config manually:"
    warn "  $export_line"
    return
  fi

  if grep -qF "$dir" "$SHELL_RC" 2>/dev/null; then
    info "$dir already in $SHELL_RC"
  else
    echo "" >> "$SHELL_RC"
    echo "# Added by skilllink installer" >> "$SHELL_RC"
    echo "$export_line" >> "$SHELL_RC"
    info "Added $dir to PATH in $SHELL_RC"
    warn "Restart your terminal or run: source $SHELL_RC"
  fi
}

if $PIPX_INSTALL; then
  : # pipx manages its own PATH via ~/.local/bin — no action needed
elif $USER_INSTALL; then
  warn "Installed to user site-packages (--user)."
  add_to_path "$USER_BIN"
elif ! command -v skilllink &>/dev/null; then
  # System install succeeded but skilllink isn't on PATH yet (e.g. pip Scripts dir not in PATH)
  warn "'skilllink' not found on PATH — attempting to locate it..."
  SKILLLINK_BIN="$(${PYTHON} -c "import shutil; print(shutil.which('skilllink') or '')" 2>/dev/null || true)"
  if [ -n "$SKILLLINK_BIN" ]; then
    add_to_path "$(dirname "$SKILLLINK_BIN")"
  else
    add_to_path "$USER_BIN"
  fi
fi

# ---- Verify ----------------------------------------------------------------
section "Verifying installation..."

# Re-source PATH in case we just updated it
export PATH="${USER_BIN}:${PATH}"

if command -v skilllink &>/dev/null; then
  info "$(skilllink --version)"
else
  warn "'skilllink' not found on PATH in this session."
  warn "Restart your terminal, then run: skilllink --version"
fi

# ---- Claude Code slash command ---------------------------------------------
section "Installing Claude Code slash command..."

CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"

if [ ! -d "$CLAUDE_DIR" ]; then
  warn "~/.claude not found — Claude Code may not be installed yet."
  warn "Once you install Claude Code, re-run this installer or copy the slash command manually:"
  warn "  mkdir -p ~/.claude/commands"
  warn "  curl -fsSL ${GITHUB_RAW_BASE}/.claude/commands/skill-this-project.md \\"
  warn "    -o ~/.claude/commands/skill-this-project.md"
else
  mkdir -p "$COMMANDS_DIR"
  if curl -fsSL "${GITHUB_RAW_BASE}/.claude/commands/skill-this-project.md" \
       -o "${COMMANDS_DIR}/skill-this-project.md" 2>/dev/null; then
    info "Slash command installed: ~/.claude/commands/skill-this-project.md"
  else
    warn "Could not download slash command. Install it manually:"
    warn "  curl -fsSL ${GITHUB_RAW_BASE}/.claude/commands/skill-this-project.md \\"
    warn "    -o ~/.claude/commands/skill-this-project.md"
  fi
fi

# ---- Done ------------------------------------------------------------------
echo ""
echo -e "${BOLD}skilllink installed successfully!${RESET}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Create your tooling directory and catalog:"
echo "       mkdir -p ~/.skilllink"
echo "       skilllink init        # start from a sample catalog"
echo "       skilllink scan        # or auto-discover existing .md tools"
echo ""
echo "  2. (Optional) Override the default tools directory:"
echo "       export SKILLLINK_TOOLING_DIR=/path/to/your/tools"
echo "     Add that line to your shell config to make it permanent."
echo ""
echo "  3. In any Claude Code project, run:"
echo "       /skill-this-project"
echo ""
echo "  Docs: ${REPO}#readme"
echo ""
