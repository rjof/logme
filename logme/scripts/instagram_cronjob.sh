#!/bin/bash
NOW=$(/bin/date +"%Y-%m-%d_%H-%M-%S")
exec 1>> /home/rjof/logme_data/logs/${NOW}_cron_instagram.log 2>&1
echo "Running cron job with daily anacron for logme instagram (6 saved posts)" 
cd /home/rjof/Documents/logme_project
source /home/rjof/virtual_environments/logme/bin/activate
python -m logme source instagram
