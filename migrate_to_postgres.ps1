# Проверяем наличие PostgreSQL
$pgVer = (Get-Command postgres -ErrorAction SilentlyContinue).Version
if (-not $pgVer) {
    Write-Host "PostgreSQL не установлен. Пожалуйста, установите PostgreSQL и добавьте его в PATH" -ForegroundColor Red
    exit 1
}

# Параметры подключения - укажите ваши реальные значения
$DB_NAME = "water_delivery_crm"
$DB_USER = "postgres"
$DB_PASSWORD = "postgres"  # Используйте пароль, который вы указали при установке PostgreSQL

# Создаем новую базу данных
Write-Host "Создаем базу данных $DB_NAME..." -ForegroundColor Green
$env:PGPASSWORD = $DB_PASSWORD
psql -U $DB_USER -c "CREATE DATABASE $DB_NAME WITH ENCODING 'UTF8';"

# Создаем резервную копию текущей SQLite базы
Write-Host "Создаем дамп данных из SQLite..." -ForegroundColor Green
python manage.py dumpdata --exclude auth.permission --exclude contenttypes --exclude admin.logentry --indent 2 > data_dump.json

# Обновляем настройки базы данных в settings.py
Write-Host "Обновляем настройки базы данных..." -ForegroundColor Green
$ENV_CONTENT = @"
DEBUG=False
SECRET_KEY=your-super-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database settings
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=localhost
DB_PORT=5432
"@
$ENV_CONTENT | Out-File -FilePath ".env" -Encoding UTF8

# Устанавливаем psycopg2
Write-Host "Устанавливаем драйвер PostgreSQL..." -ForegroundColor Green
pip install psycopg2-binary

# Применяем миграции к новой базе
Write-Host "Применяем миграции..." -ForegroundColor Green
python manage.py migrate --database=default

# Загружаем данные
Write-Host "Загружаем данные..." -ForegroundColor Green
python manage.py loaddata data_dump.json

Write-Host "Миграция завершена успешно!" -ForegroundColor Green
Write-Host "Пожалуйста, проверьте работу приложения с новой базой данных." -ForegroundColor Yellow