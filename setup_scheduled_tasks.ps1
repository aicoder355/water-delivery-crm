# Требуются права администратора для создания задач
#Requires -RunAsAdministrator

$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$backupScript = Join-Path $projectPath "backup_sqlite.ps1"
$maintenanceScript = Join-Path $projectPath "maintain_sqlite.ps1"

# Функция для создания задачи
function Register-MaintenanceTask {
    param (
        [string]$TaskName,
        [string]$ScriptPath,
        [string]$Schedule,
        [int]$DaysInterval = 1
    )

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
    
    if ($Schedule -eq "Daily") {
        $trigger = New-ScheduledTaskTrigger -Daily -DaysInterval $DaysInterval -At "03:00"
    }
    elseif ($Schedule -eq "Weekly") {
        $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "04:00"
    }

    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

    $task = Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force

    Write-Host "Задача '$TaskName' успешно создана"
}

try {
    # Создаем задачу для ежедневного бэкапа
    Register-MaintenanceTask -TaskName "WaterDeliveryCRM_Backup" -ScriptPath $backupScript -Schedule "Daily"

    # Создаем задачу для еженедельного обслуживания
    Register-MaintenanceTask -TaskName "WaterDeliveryCRM_Maintenance" -ScriptPath $maintenanceScript -Schedule "Weekly"

    Write-Host "Все задачи успешно настроены"
}
catch {
    Write-Error "Ошибка при создании задач: $_"
    exit 1
}
