# Crea en el Programador de tareas de Windows la ejecución semanal de ejecutar_programado.sh.
# Se usa en lugar de cron porque cron solo funciona con WSL abierto; Windows abre WSL solo.
#
# Ejecutar desde WSL (una sola vez):
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w programar_windows.ps1)"
# Para borrar la tarea:
#   powershell.exe -Command 'Unregister-ScheduledTask -TaskName "automatizacion-python - informe semanal" -Confirm:$false'

$nombre = "automatizacion-python - informe semanal"

# Abre WSL (Ubuntu) y ejecuta el script del proyecto.
$accion = New-ScheduledTaskAction -Execute "wsl.exe" `
    -Argument "-d Ubuntu -u administrator -- /home/administrator/automatizacion-python/ejecutar_programado.sh"

# Cada lunes a las 08:00.
$disparador = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 08:00

# Si el PC estaba apagado a esa hora, se ejecuta en cuanto se pueda.
$opciones = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $disparador -Settings $opciones `
    -Description "Procesa los archivos de ventas de datos/entrada/ y genera los informes (proyecto automatizacion-python)." | Out-Null

Get-ScheduledTask -TaskName $nombre | Select-Object TaskName, State
(Get-ScheduledTask -TaskName $nombre).Triggers | Select-Object StartBoundary, @{n="Dias";e={$_.DaysOfWeek}}
Get-ScheduledTaskInfo -TaskName $nombre | Select-Object NextRunTime
