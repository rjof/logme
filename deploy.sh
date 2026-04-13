#!/bin/bash
# deploy.sh - Run this on your development machine

PROJECT_DIR="/home/rjof/Documents/logme"
VENV_DIR="/home/rjof/virtual_environments/logme"

# 1. Load configuration from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "ERROR: .env file not found."
    exit 1
fi

# Path settings
LOCAL_COOKIE_PATH="/home/rjof/snap/firefox/common/.mozilla/firefox/8j9s4e80.default/cookies.sqlite"
REMOTE_COOKIE_PATH="/home/rjof/snap/firefox/common/.mozilla/firefox/8j9s4e80.default/cookies.sqlite"
LOCAL_CONFIG_DIR="/home/rjof/.config/logme"
REMOTE_CONFIG_DIR="/home/rjof/.config/logme"

if ! command -v sshpass &> /dev/null; then
    echo "ERROR: 'sshpass' is not installed."
    exit 1
fi

# 2. Identify the required Python version
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
TARGET_PY="python${PY_MAJOR}.${PY_MINOR}"

echo "1. Ensuring Locales and Python $TARGET_PY exist in LXC..."

sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "
    export LC_ALL=C
    if ! pct exec $LXC_ID -- dpkg -s locales > /dev/null 2>&1; then
        echo 'Installing locales in LXC...'
        pct exec $LXC_ID -- apt-get update
        pct exec $LXC_ID -- apt-get install -y locales
    fi
    echo 'Generating locales...'
    pct exec $LXC_ID -- locale-gen en_US.UTF-8
    pct exec $LXC_ID -- locale-gen es_MX.UTF-8
    pct exec $LXC_ID -- update-locale

    if ! pct exec $LXC_ID -- which $TARGET_PY > /dev/null 2>&1; then
        echo 'Required Python version $TARGET_PY not found in LXC. Attempting install...'
        pct exec $LXC_ID -- apt-get update
        pct exec $LXC_ID -- apt-get install -y $TARGET_PY ${TARGET_PY}-venv
    else
        echo 'Python $TARGET_PY is already available in LXC.'
    fi
"

echo "2. Pushing changes to GitHub..."
git push origin master

echo "3. Syncing cookies.sqlite and configuration files..."
# Sync Cookies
sshpass -p "$PROXMOX_PASSWORD" scp "$LOCAL_COOKIE_PATH" "$PROXMOX_USER@$PROXMOX_HOST:/tmp/cookies.sqlite"
sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "
    export LC_ALL=C
    pct exec $LXC_ID -- mkdir -p $(dirname "$REMOTE_COOKIE_PATH")
    pct push $LXC_ID /tmp/cookies.sqlite $REMOTE_COOKIE_PATH
    rm /tmp/cookies.sqlite
"

# Sync Config Directory
echo "Compressing and syncing $LOCAL_CONFIG_DIR..."
tar -czf /tmp/logme_config.tar.gz -C "$LOCAL_CONFIG_DIR" .
sshpass -p "$PROXMOX_PASSWORD" scp /tmp/logme_config.tar.gz "$PROXMOX_USER@$PROXMOX_HOST:/tmp/logme_config.tar.gz"
sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "
    export LC_ALL=C
    pct exec $LXC_ID -- mkdir -p $REMOTE_CONFIG_DIR
    pct push $LXC_ID /tmp/logme_config.tar.gz /tmp/logme_config.tar.gz
    pct exec $LXC_ID -- tar -xzf /tmp/logme_config.tar.gz -C $REMOTE_CONFIG_DIR
    pct exec $LXC_ID -- rm /tmp/logme_config.tar.gz
    rm /tmp/logme_config.tar.gz
"
rm /tmp/logme_config.tar.gz

echo "4. Updating LXC Code and Virtual Environment..."
sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "pct exec $LXC_ID -- bash -c '
    export LC_ALL=en_US.UTF-8
    mkdir -p \"$(dirname "$VENV_DIR")\"
    
    if [ -d \"$VENV_DIR\" ]; then
        CURRENT_VENV_VER=\$(\"$VENV_DIR/bin/python\" -c \"import sys; print(f\\\"{sys.version_info.major}.{sys.version_info.minor}\\\")\")
        if [ \"\$CURRENT_VENV_VER\" != \"${PY_MAJOR}.${PY_MINOR}\" ]; then
            echo \"Venv version mismatch. Recreating...\"
            rm -rf \"$VENV_DIR\"
        fi
    fi

    if [ ! -d \"$VENV_DIR\" ]; then
        echo \"Creating virtual environment with $TARGET_PY...\"
        $TARGET_PY -m venv \"$VENV_DIR\"
    fi
    
    cd \"$PROJECT_DIR\" || exit 1
    echo \"Configuring safe directory for git...\"
    git config --global --add safe.directory \"$PROJECT_DIR\"
    
    echo \"Pulling latest code...\"
    git pull
    
    echo \"Updating dependencies...\"
    \"$VENV_DIR/bin/python\" -m pip install --upgrade pip
    \"$VENV_DIR/bin/python\" -m pip install -r requirements.txt
'"

echo "Deployment complete."
