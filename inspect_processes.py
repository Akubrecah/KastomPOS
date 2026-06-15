import psutil
import os
import sys

print("Inspecting running Python processes...")
for p in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
    try:
        cmd = p.info['cmdline']
        if cmd and any('main.py' in x or 'uvicorn' in x or 'main_fastapi' in x for x in cmd):
            print(f"\nProcess ID: {p.info['pid']}")
            print(f"Name: {p.info['name']}")
            print(f"Cmdline: {cmd}")
            print(f"CWD: {p.info['cwd']}")
            
            # Open files
            print("Open files:")
            for f in p.open_files():
                print(f"  {f.path}")
                
            # Connections
            print("Connections:")
            for c in p.connections():
                print(f"  {c.laddr} -> {c.raddr} ({c.status})")
    except Exception as e:
        print(f"Error reading process: {e}")
