#!/bin/bash
# deploy.sh - Run this on your development machine

PROJECT_DIR="/home/rjof/Documents/logme_project"
VENV_DIR="/home/rjof/virtual_environments/logme"

# 1. Load configuration from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "ERROR: .env file not found."
    exit 1
fi

# Local path settings
LOCAL_COOKIE_PATH="/home/rjof/snap/firefox/common/.mozilla/firefox/8j9s4e80.default/cookies.sqlite"
REMOTE_COOKIE_PATH="/home/rjof/snap/firefox/common/.mozilla/firefox/8j9s4e80.default/cookies.sqlite"

if ! command -v sshpass &> /dev/null; then
    echo "ERROR: 'sshpass' is not installed."
    exit 1
fi

# 2. Identify the required Python version
# Extracts e.g., "3.12"
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
TARGET_PY="python${PY_MAJOR}.${PY_MINOR}"

echo "1. Ensuring LXC has $TARGET_PY..."

# This block runs on the Proxmox host to manage the LXC
sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "
    # Check if the specific python version exists in LXC
    if ! pct exec $LXC_ID -- which $TARGET_PY > /dev/null 2>&1; then
        echo 'Required Python version $TARGET_PY not found in LXC. Attempting install...'
        # Note: This assumes a Debian/Ubuntu based LXC
        pct exec $LXC_ID -- apt-get update
        pct exec $LXC_ID -- apt-get install -y $TARGET_PY ${TARGET_PY}-venv
    else
        echo 'Python $TARGET_PY is already available in LXC.'
    fi
"

echo "2. Pushing changes to GitHub..."
git push origin master

echo "3. Syncing cookies.sqlite..."
sshpass -p "$PROXMOX_PASSWORD" scp "$LOCAL_COOKIE_PATH" "$PROXMOX_USER@$PROXMOX_HOST:/tmp/cookies.sqlite"
sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "
    pct exec $LXC_ID -- mkdir -p $(dirname "$REMOTE_COOKIE_PATH")
    pct push $LXC_ID /tmp/cookies.sqlite $REMOTE_COOKIE_PATH
    rm /tmp/cookies.sqlite
"

echo "4. Updating LXC Code and Virtual Environment..."
sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "pct exec $LXC_ID -- bash -c '
    mkdir -p $(dirname "$VENV_DIR")
    
    # If venv exists but uses wrong version, recreate it
    if [ -d \"$VENV_DIR\" ]; then
        CURRENT_VENV_VER=\$($VENV_DIR/bin/python -c \"import sys; print(f\\\"{sys.version_info.major}.{sys.version_info.minor}\\\")\")
        if [ \"\$CURRENT_VENV_VER\" != \"${PY_MAJOR}.${PY_MINOR}\" ]; then
            echo \"Venv version mismatch (\$CURRENT_VENV_VER vs ${PY_MAJOR}.${PY_MINOR}). Recreating...\"
            rm -rf \"$VENV_DIR\"
        fi
    fi

    if [ ! -d \"$VENV_DIR\" ]; then
        echo \"Creating virtual environment with $TARGET_PY...\"
        $TARGET_PY -m venv \"$VENV_DIR\"
    fi
    
    cd \"$PROJECT_DIR\" || exit 1
    echo \"Pulling latest code...\"
    git pull
    
    echo \"Updating dependencies...\"
    \"$VENV_DIR/bin/python\" -m pip install --upgrade pip
    \"$VENV_DIR/bin/python\" -m pip install -r requirements.txt
'"

echo "Deployment complete."
