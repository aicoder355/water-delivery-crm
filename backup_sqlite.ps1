$BackupDir = "C:\Backups\water_delivery_crm"
$DateTime = Get-Date -Format "yyyy-MM-dd_HH-mm"
$BackupName = "backup_${DateTime}"
$DaysToKeep = 30
$DbPath = ".\db.sqlite3"

# Проверяем наличие директории для бэкапов
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

# Функция для проверки, не заблокирована ли база
function Test-DatabaseLock {
    try {
        $connection = New-Object System.Data.SQLite.SQLiteConnection("Data Source=$DbPath")
        $connection.Open()
        $connection.Close()
        return $false
    }
    catch {
        return $true
    }
}

# Создаем резервную копию базы данных
try {
    # Ждем, пока база освободится
    $maxAttempts = 5
    $attempt = 0
    while ((Test-DatabaseLock) -and ($attempt -lt $maxAttempts)) {
        Start-Sleep -Seconds 10
        $attempt++
    }

    # Создаем бэкап через sqlite3
    $backupPath = Join-Path $BackupDir "${BackupName}.sqlite3"
    sqlite3 $DbPath ".backup '$backupPath'"

    # Архивируем бэкап
    Compress-Archive -Path $backupPath -DestinationPath "$BackupDir\${BackupName}.zip"
    Remove-Item $backupPath

    # Архивируем статические файлы и медиа
    Compress-Archive -Path ".\staticfiles", ".\media" -DestinationPath "$BackupDir\${BackupName}_files.zip"

    # Удаляем старые бэкапы
    Get-ChildItem $BackupDir | Where-Object {
        $_.LastWriteTime -lt (Get-Date).AddDays(-$DaysToKeep)
    } | Remove-Item

    # Логируем успешное выполнение
    $successMessage = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'): Backup completed successfully"
    Add-Content -Path "$BackupDir\backup.log" -Value $successMessage

    # Проверяем размер лог файла
    $logFile = Get-Item "$BackupDir\backup.log"
    if ($logFile.Length -gt 1MB) {
        $oldContent = Get-Content "$BackupDir\backup.log" -Tail 1000
        $oldContent | Set-Content "$BackupDir\backup.log"
    }
}
catch {
    $errorMessage = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'): Backup failed: $($_.Exception.Message)"
    Add-Content -Path "$BackupDir\backup.log" -Value $errorMessage
    Write-Error $errorMessage
    exit 1
}
