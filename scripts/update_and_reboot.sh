
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

# Function: attempt to make .git writable without interactive sudo
ensure_git_writable() {
  if [ -w .git/objects ] && [ -w .git/refs ]; then
    return 0
  fi
  echo "Repairing .git permissions (sudo -n if available)…"
  if command -v sudo >/dev/null 2>&1; then
    # Non-interactive sudo attempts; if these fail they will exit non-zero without prompting
    sudo -n chown -R "$(id -u):$(id -g)" .git 2>/dev/null || true
    sudo -n chmod -R u+rwX,g+rX .git 2>/dev/null || true
  else
    chmod -R u+rwX,g+rX .git 2>/dev/null || true
  fi
  # Re-check
  if [ -w .git/objects ] && [ -w .git/refs ]; then
    echo ".git now appears writable."
    return 0
  fi
  echo "Warning: .git still not writable by current user. Git operations may fail."
  return 1
}

# Function: perform update via git (returns 0 on success)
update_via_git() {
  # Drop any local work so deployment is deterministic
  git reset --hard HEAD || true
  git clean -fd || true
  echo "Fetching latest changes from repository..."
  if ! git fetch origin 2>&1; then
    echo "git fetch failed."
    return 1
  fi
  echo "Resetting to latest remote version..."
  if ! git reset --hard origin/master 2>&1; then
    echo "git reset --hard origin/master failed."
    return 1
  fi
  echo "Successfully updated repository via git."
  return 0
}

# Function: fallback update by downloading GitHub archive and copying over files
update_via_archive() {
  echo "Falling back to archive-based update (read-only .git or git failure)."
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
  TMP_DIR="/tmp/spacex-dashboard-update-$$"
  mkdir -p "$TMP_DIR"
  # Try to detect the repo slug from git remote; else default to hwpaige/spacex-dashboard
  REPO_SLUG="hwpaige/spacex-dashboard"
  if git remote get-url origin >/dev/null 2>&1; then
    ORIGIN_URL="$(git remote get-url origin)"
    case "$ORIGIN_URL" in
      *github.com/*)
        SLUG_PART="${ORIGIN_URL##*github.com/}"
        SLUG_PART="${SLUG_PART%.git}"
        if [ -n "$SLUG_PART" ]; then REPO_SLUG="$SLUG_PART"; fi
        ;;
    esac
  fi
  ARCHIVE_URL="https://github.com/${REPO_SLUG}/archive/refs/heads/master.zip"
  echo "Downloading latest code archive from $ARCHIVE_URL ..."
  if command -v curl >/dev/null 2>&1; then
    curl -L "$ARCHIVE_URL" -o "$TMP_DIR/src.zip"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$TMP_DIR/src.zip" "$ARCHIVE_URL"
  else
    echo "Error: Neither curl nor wget is available to download archive."
    return 1
  fi
  echo "Unpacking archive..."
  if ! unzip -q "$TMP_DIR/src.zip" -d "$TMP_DIR"; then
    echo "Error: Failed to unzip downloaded archive."
    return 1
  fi
  # The zip unpacks to repo-branch directory
  SRC_DIR="$(find "$TMP_DIR" -maxdepth 1 -type d -name '*-master' -print -quit)"
  if [ -z "$SRC_DIR" ]; then
    echo "Error: Could not locate unpacked source directory."
    return 1
  fi
  echo "Synchronizing files into project directory (preserving caches and local data)..."
  # Exclusions: do not overwrite .git, cache historical files, remembered networks, last connected network, and local venv
  if command -v rsync >/dev/null 2>&1; then
    rsync -av --delete \
      --exclude '.git/' \
      --exclude 'cache/previous_launches_cache.json' \
      --exclude 'cache/previous_launches_cache_backup.json' \
      --exclude 'cache/remembered_networks.json' \
      --exclude 'cache/last_connected_network.json' \
      --exclude '.venv/' \
      "$SRC_DIR"/ "$PROJECT_DIR"/
  else
    echo "rsync not found; using cp -a fallback (no delete of removed files)."
    (cd "$SRC_DIR" && tar cf - .) | (cd "$PROJECT_DIR" && tar xf -)
  fi
  echo "Archive-based update applied."
  return 0
}

# Try to ensure .git is writable, then try git update; if it fails, use archive fallback
if ensure_git_writable && update_via_git; then
  :
else
  echo "Git-based update failed or not possible due to permissions."
  if ! update_via_archive; then
    echo "Error: Archive-based update also failed. Aborting."
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