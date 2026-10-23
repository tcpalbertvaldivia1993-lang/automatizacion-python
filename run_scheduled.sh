#!/bin/bash
# Processes every file in data/input/, moves the successful ones to
# data/input/processed/ and sends the reports by email (settings in .env).
# Saves the totals in results/history.csv to alert if they change sharply
# compared with the average of the previous 4 weeks. It's run by the Windows
# Task Scheduler (see schedule_windows.ps1), although it would also work with cron.
#
# The scheduled task starts in another folder, so first we go to the project's
# (main.py uses relative paths such as "results/").
cd "$(dirname "$0")" || exit 1
mkdir -p results

# Everything goes to results/run.log; cron.log also keeps any unexpected
# Python error that doesn't make it into the log.
venv/bin/python main.py data/input --move-processed --send-email \
    --history results/history.csv >> results/cron.log 2>&1
