# Collect static files
python manage.py collectstatic --noinput --clear

# Apply migrations
python manage.py migrate --noinput

# Create superuser if not exists
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', 'admin') if not User.objects.filter(username='admin').exists() else None"

# Start Gunicorn with SSL
gunicorn water_delivery_crm.wsgi:application -c gunicorn.conf.py \
    --certfile=/path/to/your/fullchain.pem \
    --keyfile=/path/to/your/privkey.pem
