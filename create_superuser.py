# create_superuser.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_project.settings')
django.setup()

from django.contrib.auth.models import User

# اطلاعات Superuser
USERNAME = os.environ.get('SUPERUSER_USERNAME', 'behyazd')
EMAIL = os.environ.get('SUPERUSER_EMAIL', 'behyazd@gmail.com')
PASSWORD = os.environ.get('SUPERUSER_PASSWORD', 'Behyazd@3052')

if not User.objects.filter(username=USERNAME).exists():
    User.objects.create_superuser(USERNAME, EMAIL, PASSWORD)
    print(f'✅ Superuser "{USERNAME}" created successfully!')
else:
    print(f'ℹ️ Superuser "{USERNAME}" already exists.')