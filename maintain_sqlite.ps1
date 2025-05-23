$DbPath = ".\db.sqlite3"
$BackupDir = "C:\Backups\water_delivery_crm"
$DateTime = Get-Date -Format "yyyy-MM-dd_HH-mm"
$MaintenanceLog = ".\sqlite_maintenance.log"

# Проверяем наличие sqlite3.exe
$SqlitePath = (Get-Command sqlite3.exe -ErrorAction SilentlyContinue).Source
if (-not $SqlitePath) {
    Write-Host "sqlite3.exe не найден в PATH. Пожалуйста, добавьте его в переменную среды PATH." | Tee-Object -FilePath $MaintenanceLog -Append
    exit 1
} else {
    Write-Host "Используется sqlite3.exe: $SqlitePath" | Tee-Object -FilePath $MaintenanceLog -Append
}

# Функция для логирования
function Write-Log {
    param($Message)
    $logMessage = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'): $Message"
    Add-Content -Path $MaintenanceLog -Value $logMessage
    Write-Host $logMessage
}

try {
    # Создаем временную копию базы
    Write-Log "Creating temporary backup..."
    Copy-Item $DbPath "$DbPath.bak"

    # Выполняем VACUUM
    Write-Log "Running VACUUM..."
    sqlite3 $DbPath "VACUUM;"

    # Анализируем и оптимизируем индексы
    Write-Log "Analyzing and optimizing indexes..."
    sqlite3 $DbPath @"
ANALYZE;
PRAGMA optimize;
PRAGMA auto_vacuum = FULL;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 30000000000;
"@

    # Проверяем целостность базы
    Write-Log "Checking database integrity..."
    $integrityCheck = sqlite3 $DbPath "PRAGMA integrity_check;"
    if ($integrityCheck -eq "ok") {
        Write-Log "Database integrity check passed"
        Remove-Item "$DbPath.bak"
    }
    else {
        throw "Database integrity check failed"
    }

    Write-Log "Maintenance completed successfully"
}
catch {
    Write-Log "Error during maintenance: $($_.Exception.Message)"
    if (Test-Path "$DbPath.bak") {
        Write-Log "Restoring from backup..."
        Stop-Process -Name "w3wp" -ErrorAction SilentlyContinue
        Copy-Item "$DbPath.bak" $DbPath
        Remove-Item "$DbPath.bak"
    }
    exit 1
}
