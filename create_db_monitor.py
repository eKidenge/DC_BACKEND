# create_db_monitor.py
import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DC_BACKEND.settings')
django.setup()

from django.db import connection
from django.apps import apps

def monitor_database():
    print("Monitoring database changes...")
    print("=" * 50)
    
    # Get initial state
    models = apps.get_models()
    initial_counts = {model.__name__: model.objects.count() for model in models}
    
    while True:
        time.sleep(5)  # Check every 5 seconds
        
        current_counts = {model.__name__: model.objects.count() for model in models}
        
        for model_name in current_counts:
            if current_counts[model_name] != initial_counts.get(model_name, 0):
                print(f"[{time.ctime()}] {model_name}: {initial_counts[model_name]} -> {current_counts[model_name]}")
                initial_counts[model_name] = current_counts[model_name]
        
        # Check SQL queries
        if len(connection.queries) > 0:
            print(f"\nRecent queries:")
            for query in connection.queries[-5:]:
                print(f"  {query['sql'][:100]}...")

if __name__ == "__main__":
    monitor_database()
