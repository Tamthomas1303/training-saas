#!/usr/bin/env bash
# Build script cho Render (Root Directory: backend). Khop voi Build Command trong
# 04_HUONG_DAN_DEPLOY.md Phan 2. Start Command rieng: gunicorn config.wsgi:application
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
