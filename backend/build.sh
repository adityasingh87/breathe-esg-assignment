#!/usr/bin/env bash
# Render build script for Django backend
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py seed_db
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin'); print('Admin user ready.')"
