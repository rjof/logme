# Deployment Documentation

This document explains how to deploy the `logme` project to a Proxmox LXC container and schedule the automated Instagram ingestion.

## Overview

The deployment process is automated via a `deploy.sh` script on the development machine. It ensures that the LXC container mirrors the development environment, syncs the latest code from GitHub, and updates the Instagram session cookies.

## Prerequisites

### 1. Development Machine
- **sshpass**: Required for automated SSH password authentication.
  ```bash
  sudo apt install sshpass
  ```
- **.env File**: Create a `.env` file in the project root with the following parameters:
  ```env
  # Proxmox/LXC Configuration
  PROXMOX_USER=root
  PROXMOX_HOST=192.168.1.XX
  PROXMOX_PASSWORD=your_secure_password
  LXC_ID=100

  # Instagram Credentials (used by run_instagram.sh in LXC)
  instagram_user=your_username
  instagram_password=your_password
  ```

### 2. Proxmox LXC Container (Ubuntu 24.04 Setup)

#### Firefox Installation (Avoid Snap)
Ubuntu 24.04 LXCs struggle with the default Snap-based Firefox. Use the Mozilla Team PPA instead:
```bash
# Inside LXC as root
add-apt-repository ppa:mozillateam/ppa -y

# Pin the PPA to prevent Snap transition
echo '
Package: *
Pin: release o=LP-PPA-mozillateam
Pin-Priority: 1001
' | tee /etc/apt/preferences.d/mozilla-firefox

apt update
apt install -y firefox
```

#### Geckodriver Installation
```bash
# Inside LXC as root
wget https://github.com/mozilla/geckodriver/releases/download/v0.34.0/geckodriver-v0.34.0-linux64.tar.gz
tar -xvzf geckodriver-v0.34.0-linux64.tar.gz
mv geckodriver /usr/local/bin/
chmod +x /usr/local/bin/geckodriver
rm geckodriver-v0.34.0-linux64.tar.gz
```

#### Mounting External HDD (Proxmox Bind Mount)
To save downloaded posts to an external USB-C drive, use a bind mount from the Proxmox host.

**Step A: On the Proxmox Host**
1. Identify the drive UUID: `blkid /dev/sdX1`
2. Create mount point: `mkdir -p /mnt/external_toshiba`
3. Add to `/etc/fstab`:
   `UUID=YOUR-UUID /mnt/external_toshiba auto nosuid,nodev,nofail 0 0`
4. Mount: `mount -a`
5. Pass to LXC (replace `<VMID>`):
   `pct set <VMID> -mp0 /mnt/external_toshiba,mp=/media/rjof/toshiba`

**Step B: Inside the LXC Container**
```bash
# Ensure mount point exists and set permissions
mkdir -p /media/rjof/toshiba
chown -R rjof:rjof /media/rjof/toshiba
```

## Deployment Steps

1.  **Grant Execution Permissions**:
    ```bash
    chmod +x deploy.sh
    ```
2.  **Run Deployment**:
    ```bash
    ./deploy.sh
    ```

### What `deploy.sh` does:
1.  **Version Parity**: Detects the local Python version and ensures it's installed in the LXC container.
2.  **Code Sync**: Pushes local changes to GitHub and triggers a `git pull` inside the LXC.
3.  **Cookie Sync**: Copies your active Firefox `cookies.sqlite` from the development machine to the LXC container to bypass Instagram login challenges.
4.  **Environment Management**: Creates or updates the virtual environment (`/home/rjof/virtual_environments/logme`) and installs dependencies.

## LXC Execution & Scheduling

The Instagram ingestion is handled by `run_instagram.sh` inside the LXC container.

### 1. `run_instagram.sh`
This script:
- Loads credentials from the LXC's local `.env`.
- Generates a random post count (amount) between 3 and 9.
- Executes the ingestion command.
- Logs output to `/home/rjof/logme_data/logs/cron_instagram.log`.

### 2. Scheduling (Cron Job)
To run the ingestor daily at a random time between 12:00 and 18:00, add the following to your LXC crontab (`crontab -e`):

```cron
0 12 * * * /usr/bin/sleep $((RANDOM % 21600)) && /home/rjof/Documents/logme_project/run_instagram.sh
```

## Maintenance

- **Cookie Expiry**: If the ingestor starts failing with login errors, simply run `./deploy.sh` while logged into Instagram in your development Firefox browser to refresh the synced cookies.
- **Logs**: Monitor the execution by checking the log file in the LXC container:
  ```bash
  tail -f /home/rjof/logme_data/logs/cron_instagram.log
  ```
