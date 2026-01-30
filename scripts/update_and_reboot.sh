
# Hardened git-only updater (no ZIP fallback)
# Writes progress to stdout (app redirects to /tmp/spacex-dashboard-update.log)

echo "== BEGIN UPDATE (git-only) v2.3 =="
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

# Check if we're in a git repository (any subdirectory of the repo is fine)
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository. Please run this script from the spacex-dashboard directory."
    exit 1
fi

echo "Preparing repository for clean update (dropping local changes)…"

# Resolve the repository root and operate from there so running this script from scripts/ works
REPO_DIR="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_DIR" ] || [ ! -d "$REPO_DIR/.git" ]; then
  echo "Error: Failed to resolve repository root (.git not found)."; exit 1
fi
echo "Repository root resolved to: $REPO_DIR"
cd "$REPO_DIR" || { echo "Error: Unable to cd to $REPO_DIR"; exit 1; }

# Determine the desktop/effective user (so git writes to .git as the right user)
EFFECTIVE_USER="${SUDO_USER:-$(whoami)}"
EFFECTIVE_HOME=$(getent passwd "$EFFECTIVE_USER" 2>/dev/null | cut -d: -f6)
[ -z "$EFFECTIVE_HOME" ] && EFFECTIVE_HOME="/home/$EFFECTIVE_USER"

# Helper to run git consistently as the effective (non-root) user
run_git() {
  if [ "$(whoami)" = "root" ] || [ -n "${SUDO_USER}" ]; then
    sudo -u "$EFFECTIVE_USER" -H git "$@"
  else
    git "$@"
  fi
}

# Mark repo as safe for BOTH current user (may be root) and the effective desktop user
git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true
if [ "$(whoami)" = "root" ] || [ -n "${SUDO_USER}" ]; then
  sudo -u "$EFFECTIVE_USER" -H git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true
fi

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

# Function: perform update via git as EFFECTIVE_USER (returns 0 on success)
update_via_git() {
  local target_branch="${1:-master}"
  
  # Drop any local work so deployment is deterministic
  run_git reset --hard HEAD || true
  run_git clean -fd || true
  
  echo "Fetching latest changes from repository..."
  if ! run_git fetch origin 2>&1; then
    echo "git fetch failed."
    return 1
  fi
  
  echo "Checking out/resetting to branch: $target_branch"
  if ! run_git checkout "$target_branch" 2>&1; then
    echo "Warning: git checkout $target_branch failed, attempting to reset directly to origin/$target_branch"
  fi
  
  echo "Resetting to latest remote version of origin/$target_branch..."
  if ! run_git reset --hard "origin/$target_branch" 2>&1; then
    echo "git reset --hard origin/$target_branch failed."
    return 1
  fi
  
  echo "Successfully updated repository to $target_branch via git."
  return 0
}

# Note: We intentionally avoid running git as root to sidestep "dubious ownership" and .git write issues.
# If update_via_git fails after a permission repair attempt, we abort with guidance.

TARGET_BRANCH="${1:-master}"
echo "Target update branch: $TARGET_BRANCH"

# Try to ensure repo is writable, then try git update; if it fails, try sudo-elevated git; otherwise stop with guidance
if ensure_repo_writable && update_via_git "$TARGET_BRANCH"; then
  :
else
  echo "ERROR: Unable to update repository via git due to permissions."
  echo "To fix permanently, run once on the Pi (inside the repo):"
  echo "  sudo chown -R $EFFECTIVE_USER:$EFFECTIVE_USER $REPO_DIR"
  echo "  sudo chmod -R u+rwX,g+rX .git"
  echo "Then try the update again from the app."
  echo "== END UPDATE (FAILED) =="
  exit 1
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
# Preserve F1 caches and other durable assets (e.g., generated track maps)
echo "Clearing cache (preserving previous launches, F1 track maps, and durable caches)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# Remove contents safely even if directory is empty
if [ -d "$PROJECT_DIR/cache" ]; then
    # Preserve previous launch caches which are relatively static
    # Preserve F1 track map images under cache/tracks (they are expensive to regenerate)
    # Note: F1 schedule/standings JSON caches are stored under ~/.cache/spacex-dashboard and are not touched here
    find "$PROJECT_DIR/cache" \
        -mindepth 1 -maxdepth 1 \
        -not -name 'previous_launches_cache.json' \
        -not -name 'previous_launches_cache_backup.json' \
        -not -name 'upcoming_launches_cache.json' \
        -not -name 'trajectory_cache.json' \
        -not -name 'remembered_networks.json' \
        -not -name 'last_connected_network.json' \
        -not -name 'tracks' \
        -exec rm -rf {} + 2>/dev/null || true
fi

# Reapply display settings for Pi with Waveshare 11.9" display (320x1480 rotated to portrait)
echo "Checking for Raspberry Pi display configuration..."
if [ -f "/proc/device-tree/model" ] && grep -q "Raspberry Pi" "/proc/device-tree/model" 2>/dev/null; then
    echo "Raspberry Pi detected. Reapplying display rotation for Waveshare 11.9\" (320x1480) display..."
    # Wait a moment for X session to be ready
    sleep 2
    # Detect correct HDMI output name (HDMI-A-1 on Pi 5 KMS, HDMI-1 on others)
    OUTPUT=$(xrandr | grep -E "^HDMI-A?-1 connected" | cut -d' ' -f1)
    if [ -z "$OUTPUT" ]; then
        # Fallback to first connected output if HDMI-1/HDMI-A-1 not found
        OUTPUT=$(xrandr | grep " connected" | cut -d' ' -f1 | head -n1)
    fi

    if [ -n "$OUTPUT" ]; then
        echo "Detected display output: $OUTPUT"
        # Only apply rotation for the small display (Waveshare 11.9") if explicitly configured or detected
        # By default, we use 'left' rotation for the small display and 'normal' for the large display
        if [ "$DASHBOARD_WIDTH" = "1480" ] || grep -q "max_framebuffer_height=320" /boot/firmware/config.txt 2>/dev/null; then
            echo "Applying 'left' rotation for small display..."
            xrandr --output "$OUTPUT" --rotate left 2>&1 | tee -a ~/xrandr_update.log || echo "Warning: xrandr rotation failed"
        else
            echo "Applying 'normal' rotation..."
            xrandr --output "$OUTPUT" --rotate normal 2>&1 | tee -a ~/xrandr_update.log || echo "Warning: xrandr rotation failed"
        fi
        echo "Display settings applied. If the app still scales incorrectly, you may need to rerun the setup script manually."
    else
        echo "No connected HDMI display detected. Skipping display setup."
    fi
else
    echo "Not a Raspberry Pi or model file not found. Skipping display setup."
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
echo "== END UPDATE (REBOOT ISSUED) =="