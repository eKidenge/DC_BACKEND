#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DC_BACKEND.settings')
    
    # Auto-create admin user on Render
    if os.environ.get('RENDER'):
        try:
            import django
            django.setup()
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            if not User.objects.filter(username='admin').exists():
                User.objects.create_superuser(
                    username='admin',
                    email='admin@directconnect.com',
                    password='admin123'
                )
                print("=" * 50)
                print("✅ ADMIN USER CREATED")
                print("Username: admin")
                print("Password: admin123")
                print("=" * 50)
        except Exception as e:
            print(f"Note: {e}")
    
    # Run the actual command
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
