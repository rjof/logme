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

### 2. Proxmox LXC Container
- **Firefox & Geckodriver**: Must be installed for Selenium to run in headless mode.
- **Git**: Must be installed and configured to pull from your repository.
- **Python 3**: The container should support the same Python version as your development machine (the deploy script will attempt to install the correct version if missing).

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
