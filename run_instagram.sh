#!/bin/bash
# run_instagram.sh - Managed by logme project
# Handles daily randomized Instagram ingestion

PROJECT_DIR="/home/rjof/Documents/logme"
VENV_PYTHON="/home/rjof/virtual_environments/logme/bin/python"
LOG_FILE="/home/rjof/logme_data/logs/cron_instagram.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

cd "$PROJECT_DIR" || { echo "Could not cd to $PROJECT_DIR"; exit 1; }

# 1. Load credentials from .env
if [ -f .env ]; then
    # Export variables, ignoring comments
    export $(grep -v '^#' .env | xargs)
else
    echo "$(date): ERROR - .env file not found at $PROJECT_DIR/.env" >> "$LOG_FILE"
    exit 1
fi

# 2. Generate random amount between 3 and 9
# $((RANDOM % 7)) is 0-6, + 3 is 3-9
AMOUNT=$(( ( RANDOM % 7 )  + 3 ))

# 3. Execute the command
echo "--- Starting Instagram Run: $(date) ---" >> "$LOG_FILE"
echo "Target Amount: $AMOUNT" >> "$LOG_FILE"

# Run with the virtualenv python
$VENV_PYTHON -m logme source instagram --amount "$AMOUNT" >> "$LOG_FILE" 2>&1

echo "--- Finished Run: $(date) ---" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
