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
LOCAL_INSTA_SESSION="/home/rjof/.config/instaloader/session-errejotaoefe"
REMOTE_INSTA_SESSION="/home/rjof/.config/instaloader/session-errejotaoefe"

if ! command -v sshpass &> /dev/null; then
    echo "ERROR: 'sshpass' is not installed."
    exit 1
fi

# 2. Identify the required Python version
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
TARGET_PY="python${PY_MAJOR}.${PY_MINOR}"

echo "1. Ensuring Locales, User rjof, and Python $TARGET_PY exist in LXC..."

sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "
    export LC_ALL=C
    export DEBIAN_FRONTEND=noninteractive
    
    echo \"Checking for user rjof...\"
    if ! pct exec $LXC_ID -- id -u rjof > /dev/null 2>&1; then
        echo \"Creating user rjof...\"
        pct exec $LXC_ID -- useradd -m -s /bin/bash rjof
        pct exec $LXC_ID -- usermod -aG sudo rjof
    else
        echo \"User rjof already exists.\"
    fi

    # Ensure rjof owns their home directory and everything in it
    echo \"Fixing permissions for /home/rjof...\"
    pct exec $LXC_ID -- chown -R rjof:rjof /home/rjof

    if ! pct exec $LXC_ID -- dpkg -s locales > /dev/null 2>&1; then
        echo \"Installing locales in LXC...\"
        pct exec $LXC_ID -- apt-get update
        pct exec $LXC_ID -- apt-get install -y locales
    fi
    echo \"Generating locales...\"
    pct exec $LXC_ID -- locale-gen en_US.UTF-8
    pct exec $LXC_ID -- locale-gen es_MX.UTF-8
    pct exec $LXC_ID -- update-locale

    if ! pct exec $LXC_ID -- which $TARGET_PY > /dev/null 2>&1; then
        echo \"Required Python version $TARGET_PY not found in LXC. Attempting install...\"
        pct exec $LXC_ID -- apt-get update
        pct exec $LXC_ID -- apt-get install -y $TARGET_PY ${TARGET_PY}-venv
    else
        echo \"Python $TARGET_PY is already available in LXC.\"
    fi

    echo \"Installing Firefox, Google Chrome (Non-snap) and dependencies...\"
    pct exec $LXC_ID -- apt-get update
    pct exec $LXC_ID -- apt-get install -y firefox curl wget gnupg unzip
    
    # Install Google Chrome via .deb to avoid snapd issues
    pct exec $LXC_ID -- bash -c '
        if ! which google-chrome > /dev/null 2>&1; then
            echo \"Downloading Google Chrome...\"
            wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
            apt-get install -y ./google-chrome-stable_current_amd64.deb
            rm google-chrome-stable_current_amd64.deb
        else
            echo \"Google Chrome already installed.\"
        fi
    '

    echo \"Installing Geckodriver manually...\"
    pct exec $LXC_ID -- bash -c '
        if ! which geckodriver > /dev/null 2>&1; then
            echo \"Downloading latest geckodriver...\"
            V=\$(curl -s https://api.github.com/repos/mozilla/geckodriver/releases/latest | grep \"tag_name\" | cut -d \"\\\"\" -f 4)
            URL=\"https://github.com/mozilla/geckodriver/releases/download/\$V/geckodriver-\$V-linux64.tar.gz\"
            curl -L \"\$URL\" | tar xz -C /usr/local/bin
            chmod +x /usr/local/bin/geckodriver
            echo \"Geckodriver installed successfully.\"
        else
            echo \"Geckodriver already installed.\"
        fi
    '

    echo \"Installing Chromedriver manually...\"
    pct exec $LXC_ID -- bash -c '
        if ! which chromedriver > /dev/null 2>&1; then
            echo \"Downloading latest chromedriver...\"
            # This gets the latest stable version for Chrome for Testing
            V=\$(curl -s https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | grep -oP \"(?<=\\\"version\\\": \\\")[^\\\"]+\" | head -1)
            URL=\"https://storage.googleapis.com/chrome-for-testing-public/\$V/linux64/chromedriver-linux64.zip\"
            curl -L -o /tmp/chromedriver.zip \"\$URL\"
            unzip -j /tmp/chromedriver.zip \"chromedriver-linux64/chromedriver\" -d /usr/local/bin/
            chmod +x /usr/local/bin/chromedriver
            rm /tmp/chromedriver.zip
            echo \"Chromedriver installed successfully.\"
        else
            echo \"Chromedriver already installed.\"
        fi
    '
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
    pct exec $LXC_ID -- chown rjof:rjof $REMOTE_COOKIE_PATH
    rm /tmp/cookies.sqlite
"

# Sync Instaloader Session
echo "Syncing Instaloader session..."
sshpass -p "$PROXMOX_PASSWORD" scp "$LOCAL_INSTA_SESSION" "$PROXMOX_USER@$PROXMOX_HOST:/tmp/session-errejotaoefe"
sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "
    export LC_ALL=C
    pct exec $LXC_ID -- mkdir -p $(dirname "$REMOTE_INSTA_SESSION")
    pct push $LXC_ID /tmp/session-errejotaoefe $REMOTE_INSTA_SESSION
    pct exec $LXC_ID -- chown rjof:rjof $REMOTE_INSTA_SESSION
    rm /tmp/session-errejotaoefe
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
    pct exec $LXC_ID -- chown -R rjof:rjof $REMOTE_CONFIG_DIR
    pct exec $LXC_ID -- rm /tmp/logme_config.tar.gz
    rm /tmp/logme_config.tar.gz
"
rm /tmp/logme_config.tar.gz

# Sync .env
echo "Syncing .env file..."
sshpass -p "$PROXMOX_PASSWORD" scp .env "$PROXMOX_USER@$PROXMOX_HOST:/tmp/.env"
sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "
    export LC_ALL=C
    pct push $LXC_ID /tmp/.env /home/rjof/Documents/logme/.env
    pct exec $LXC_ID -- chown rjof:rjof /home/rjof/Documents/logme/.env
    rm /tmp/.env
"

echo "4. Updating LXC Code and Virtual Environment..."
sshpass -p "$PROXMOX_PASSWORD" ssh "$PROXMOX_USER@$PROXMOX_HOST" "pct exec $LXC_ID -- su - rjof -c 'bash -s' << 'EOF_INNER'
    VENV_DIR=\"/home/rjof/virtual_environments/logme\"
    PROJECT_DIR=\"/home/rjof/Documents/logme\"
    
    # Load .env variables
    if [ -f \"\$PROJECT_DIR/.env\" ]; then
        export \$(grep -v '^#' \"\$PROJECT_DIR/.env\" | xargs)
    fi
    export LC_ALL=en_US.UTF-8
    
    mkdir -p \"\$(dirname \"\$VENV_DIR\")\"
    
    if [ -d \"\$VENV_DIR\" ]; then
        CURRENT_VENV_VER=\$(\"\$VENV_DIR/bin/python\" -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')
        if [ \"\$CURRENT_VENV_VER\" != \"${PY_MAJOR}.${PY_MINOR}\" ]; then
            echo 'Venv version mismatch. Recreating...'
            rm -rf \"\$VENV_DIR\"
        fi
    fi

    if [ ! -d \"\$VENV_DIR\" ]; then
        echo \"Creating virtual environment with $TARGET_PY...\"
        $TARGET_PY -m venv \"\$VENV_DIR\"
    fi
    
    echo 'Checking for SSH keys...'
    if [ ! -f ~/.ssh/id_ed25519 ]; then
        echo 'Generating new SSH key...'
        mkdir -p ~/.ssh
        chmod 700 ~/.ssh
        ssh-keygen -t ed25519 -C 'lxc-logme-deploy' -N '' -f ~/.ssh/id_ed25519
        echo '-------------------------------------------------------'
        echo 'NEW SSH KEY GENERATED. Please add this to GitHub:'
        cat ~/.ssh/id_ed25519.pub
        echo '-------------------------------------------------------'
        echo 'Waiting 10 seconds for you to copy it...'
        sleep 10
    else
        echo 'SSH key already exists.'
    fi

    mkdir -p \"\$PROJECT_DIR\"
    cd \"\$PROJECT_DIR\" || exit 1
    
    if [ ! -d .git ]; then
        echo 'Initializing git repository...'
        git init
        git remote add origin 'git@github.com:rjof/logme.git'
    fi

    echo 'Configuring safe directory for git...'
    git config --global --add safe.directory \"\$PROJECT_DIR\"
    
    # Ensure remote is SSH
    CURRENT_REMOTE=\$(git remote get-url origin 2>/dev/null)
    if [[ \$CURRENT_REMOTE == https* ]]; then
        echo \"Converting HTTPS remote to SSH...\"
        REPO_PATH=\$(echo \$CURRENT_REMOTE | sed 's|https://github.com/||')
        git remote set-url origin \"git@github.com:\${REPO_PATH}\"
    fi

    echo 'Pulling latest code...'
    git fetch origin master
    git reset --hard origin/master
    
    echo 'Making run_instagram.sh executable...'
    chmod +x run_instagram.sh
    
    echo 'Updating dependencies...'
    \"\$VENV_DIR/bin/python\" -m pip install --upgrade pip
    \"\$VENV_DIR/bin/python\" -m pip install -r requirements.txt
EOF_INNER
"
echo "Deployment complete."
