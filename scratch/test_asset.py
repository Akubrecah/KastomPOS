import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://demo1.jipos.co/assets/dist/css/adminlte.min.css"
print(f"Fetching asset {url}...")
try:
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req, context=ctx) as response:
        print(f"Status: {response.status}")
        html = response.read()
        print(f"Content Length: {len(html)}")
        print(f"Starts with: {html[:100].decode('utf-8', errors='ignore')!r}")
except Exception as e:
    print(f"Error: {e}")
