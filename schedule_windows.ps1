# Creates the weekly run of run_scheduled.sh in the Windows Task Scheduler.
# Used instead of cron because cron only works while WSL is open; Windows opens WSL by itself.
#
# Run from WSL (only once):
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w schedule_windows.ps1)"
# To delete the task:
#   powershell.exe -Command 'Unregister-ScheduledTask -TaskName "automatizacion-python - weekly report" -Confirm:$false'

$name = "automatizacion-python - weekly report"

# Opens WSL (Ubuntu) and runs the project's script.
$action = New-ScheduledTaskAction -Execute "wsl.exe" `
    -Argument "-d Ubuntu -u administrator -- /home/administrator/automatizacion-python/run_scheduled.sh"

# Every Monday at 08:00.
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 08:00

# If the PC was off at that time, it runs as soon as possible.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
    -Description "Processes the sales files in data/input/ and generates the reports (automatizacion-python project)." | Out-Null

Get-ScheduledTask -TaskName $name | Select-Object TaskName, State
(Get-ScheduledTask -TaskName $name).Triggers | Select-Object StartBoundary, @{n="Days";e={$_.DaysOfWeek}}
Get-ScheduledTaskInfo -TaskName $name | Select-Object NextRunTime
