#!/usr/bin/env bash

# ========================= spacex-dashboard updater =========================
# Version: 2.2 (git-only, no ZIP fallback)
# This script updates the repository using git only and reboots the device.
# It is hardened against being invoked with sudo by ensuring git writes as the
# real desktop user. All output is intended to be tailed by the app overlay.
# ============================================================================

set -o pipefail

echo "== BEGIN UPDATE (git-only) v2.2 =="

# Discover effective, non-root user for git operations
EFFECTIVE_USER="${SUDO_USER:-$(whoami)}"
if [ -n "$SUDO_USER" ] && [ "$EFFECTIVE_USER" = "root" ]; then
  # Sometimes SUDO_USER can be root when invoked from root shell; try logname
  EFFECTIVE_USER=$(logname 2>/dev/null || echo "$(whoami)")
fi

# Resolve home directory for EFFECTIVE_USER (used by git config)
if command -v getent >/dev/null 2>&1; then
  EFFECTIVE_HOME="$(getent passwd "$EFFECTIVE_USER" | cut -d: -f6)"
fi
EFFECTIVE_HOME="${EFFECTIVE_HOME:-$HOME}"
echo "Updater running as: $(whoami); git user: ${EFFECTIVE_USER}; HOME=${EFFECTIVE_HOME}"

# Ensure HOME points to the effective user when we run git as them
export HOME="$EFFECTIVE_HOME"

# Stop any running instances of the app
echo "Checking for running app instances..."
# Allow the GUI to remain open showing the in-app update overlay when requested.
# The launcher (app.py) sets KEEP_APP_RUNNING=1 to keep the UI alive so users don't
# see the greeter. If not set, fall back to the old behavior and stop the app.
if [ "${KEEP_APP_RUNNING}" = "1" ]; then
    echo "KEEP_APP_RUNNING=1 detected; not killing running app. Proceeding with update while UI shows progress."
else
    if pgrep -f "python.*app.py" > /dev/null; then
        echo "Stopping running app instances..."
        pkill -f "python.*app.py"
        sleep 2  # Wait for processes to terminate
    fi
fi

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository. Please run this script from the spacex-dashboard directory."
    exit 1
fi

echo "Preparing repository for clean update (dropping local changes)…"

# Mark repo as safe (handles cases where ownership changed previously)
git config --global --add safe.directory "$(pwd)" 2>/dev/null || true

CURRENT_UID="$(id -u "$EFFECTIVE_USER" 2>/dev/null || id -u)"; CURRENT_GID="$(id -g "$EFFECTIVE_USER" 2>/dev/null || id -g)"

# Function: attempt to make repo (including .git) writable without interactive sudo
ensure_repo_writable() {
  if [ -w .git/objects ] && [ -w .git/refs ] && [ -w . ]; then
    return 0
  fi
  echo "Attempting repo permission repair (sudo -n if available)…"
  if command -v sudo >/dev/null 2>&1; then
    # Validate that sudo can run non-interactively
    if sudo -n true 2>/dev/null; then
      sudo -n chown -R "${CURRENT_UID}:${CURRENT_GID}" . 2>/dev/null || true
      sudo -n chmod -R u+rwX,g+rX .git 2>/dev/null || true
    else
      echo "Note: sudo exists but requires a password; cannot change ownership automatically."
      chmod -R u+rwX,g+rX .git 2>/dev/null || true
    fi
  else
    chmod -R u+rwX,g+rX .git 2>/dev/null || true
  fi
  # Re-check
  if [ -w .git/objects ] && [ -w .git/refs ] && [ -w . ]; then
    echo "Repository now appears writable."
    return 0
  fi
  echo "Warning: Repository is still not writable by the current user."
  return 1
}

# Function: perform update via git (returns 0 on success)
update_via_git() {
  # Drop any local work so deployment is deterministic
  sudo -u "$EFFECTIVE_USER" git reset --hard HEAD || true
  sudo -u "$EFFECTIVE_USER" git clean -fd || true
  echo "Fetching latest changes from repository as ${EFFECTIVE_USER}..."
  if ! sudo -u "$EFFECTIVE_USER" git fetch origin 2>&1; then
    echo "git fetch failed."
    return 1
  fi
  echo "Resetting to latest remote version as ${EFFECTIVE_USER}..."
  if ! sudo -u "$EFFECTIVE_USER" git reset --hard origin/master 2>&1; then
    echo "git reset --hard origin/master failed."
    return 1
  fi
  echo "Successfully updated repository via git as ${EFFECTIVE_USER}."
  return 0
}

# Function: perform update by elevating git commands with sudo when repo is root-owned
update_via_sudo_git() {
  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo not available; cannot elevate git operations."
    return 1
  fi
  if ! sudo -n true 2>/dev/null; then
    echo "sudo requires a password; cannot elevate git operations non-interactively."
    return 1
  fi
  echo "Attempting git update with sudo (root-owned repo)…"
  sudo -n -u "$EFFECTIVE_USER" git reset --hard HEAD || true
  sudo -n -u "$EFFECTIVE_USER" git clean -fd || true
  if ! sudo -n -u "$EFFECTIVE_USER" git fetch origin 2>&1; then
    echo "sudo git fetch failed."
    return 1
  fi
  if ! sudo -n -u "$EFFECTIVE_USER" git reset --hard origin/master 2>&1; then
    echo "sudo git reset --hard origin/master failed."
    return 1
  fi
  # After updating as root, restore ownership to current user to avoid future permission drift
  sudo -n chown -R "${CURRENT_UID}:${CURRENT_GID}" . 2>/dev/null || true
  echo "Successfully updated repository via sudo git, ownership restored."
  return 0
}

# Try to ensure repo is writable, then try git update; if it fails, try sudo-elevated git; otherwise stop with guidance
if ensure_repo_writable && update_via_git; then
  :
else
  echo "Git update as current user failed. Checking for sudo-elevated git path…"
  if update_via_sudo_git; then
    :
  else
    echo "ERROR: Unable to update repository due to permissions."
    echo "To fix permanently, run once on the Pi:"
    echo "  sudo chown -R $(whoami):$(whoami) $(pwd)"
    echo "Or configure passwordless sudo for chown and reboot operations."
    exit 1
  fi
fi

# Optional: Install any new Python dependencies if requirements.txt changed
if git diff HEAD~1 --name-only | grep -q "^requirements.txt$"; then
    echo "requirements.txt changed. Installing dependencies in virtual environment..."

    # Resolve project directory for absolute paths
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

    # Find a Python interpreter
    PYTHON_BIN="$(command -v python3 || command -v python)"
    if [ -z "$PYTHON_BIN" ]; then
        echo "Error: Python is not installed. Cannot create virtual environment."
        exit 1
    fi

    VENV_DIR="$PROJECT_DIR/.venv"
    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating virtual environment at $VENV_DIR..."
        "$PYTHON_BIN" -m venv "$VENV_DIR" || {
            echo "Error: Failed to create virtual environment."; exit 1; }
    fi

    # Use the venv's python/pip to avoid PEP 668 issues on Debian/Ubuntu/Raspberry Pi
    VENV_PY="$VENV_DIR/bin/python"
    VENV_PIP="$VENV_DIR/bin/pip"

    if [ ! -x "$VENV_PY" ]; then
        echo "Error: Virtual environment python not found at $VENV_PY"
        exit 1
    fi

    echo "Upgrading pip, setuptools, and wheel in venv..."
    "$VENV_PY" -m pip install --upgrade pip setuptools wheel || {
        echo "Warning: Failed to upgrade pip tooling in venv"; }

    echo "Installing requirements from $PROJECT_DIR/requirements.txt ..."
    "$VENV_PIP" install -r "$PROJECT_DIR/requirements.txt" || {
        echo "Error: Failed to install Python dependencies in venv."; exit 1; }
fi

# Clear the cache to ensure fresh data after update, but keep relatively static caches
echo "Clearing cache (preserving previous launches and race caches)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# Remove contents safely even if directory is empty
if [ -d "$PROJECT_DIR/cache" ]; then
    # Preserve previous launch caches which are relatively static
    # Note: F1/race caches are stored under ~/.cache/spacex-dashboard and are not touched here
    find "$PROJECT_DIR/cache" \
        -mindepth 1 -maxdepth 1 \
        -not -name 'previous_launches_cache.json' \
        -not -name 'previous_launches_cache_backup.json' \
        -exec rm -rf {} + 2>/dev/null || true
fi

echo "Update complete. Rebooting system in 5 seconds..."
echo "Press Ctrl+C to cancel reboot."

# Countdown before reboot
for i in 5 4 3 2 1; do
    echo "Rebooting in $i..."
    sleep 1
done

echo "Rebooting now..."
# Try non-interactive sudo first, then fall back to common reboot commands
if command -v sudo >/dev/null 2>&1; then
  sudo -n reboot >/dev/null 2>&1 || true
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl reboot >/dev/null 2>&1 || true
fi
if command -v shutdown >/dev/null 2>&1; then
  shutdown -r now >/dev/null 2>&1 || true
fi
if [ -x /sbin/reboot ]; then
  /sbin/reboot >/dev/null 2>&1 || true
fi

echo "Reboot command may require sudo privileges. If the device does not reboot, please reboot manually."
echo "== END UPDATE =="