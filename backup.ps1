# Параметры
$BackupDir = "C:\Backups\water_delivery_crm"
$DateTime = Get-Date -Format "yyyy-MM-dd_HH-mm"
$BackupName = "backup_${DateTime}"
$DaysToKeep = 30

# Создаем директорию для бэкапов если её нет
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir
}

# Создаем бэкап базы данных
$Env:PGPASSWORD = "your-password"
pg_dump -h localhost -U postgres -d water_delivery_crm -F c -f "$BackupDir\${BackupName}.dump"

# Архивируем статические файлы и медиа
Compress-Archive -Path ".\staticfiles", ".\media" -DestinationPath "$BackupDir\${BackupName}_files.zip"

# Удаляем старые бэкапы
Get-ChildItem $BackupDir | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-$DaysToKeep)} | Remove-Item

# Логируем результат
$LogMessage = "Backup completed at $(Get-Date)"
Add-Content -Path "$BackupDir\backup.log" -Value $LogMessage

# Отправляем уведомление об успешном бэкапе
$EmailFrom = "your-email@example.com"
$EmailTo = "admin@example.com"
$Subject = "Database Backup Completed"
$Body = "Backup completed successfully. Backup files: ${BackupName}"
$SMTPServer = "smtp.example.com"

Send-MailMessage -From $EmailFrom -To $EmailTo -Subject $Subject -Body $Body -SmtpServer $SMTPServer
