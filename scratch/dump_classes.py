import models
import inspect

print("--- ALL CLASSES IN models.py ---")
for name, obj in inspect.getmembers(models, inspect.isclass):
    if obj.__module__ == 'models':
        print(name)
