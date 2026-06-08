import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://demo1.jipos.co/assets/dist/css/custom.css"
print(f"Fetching custom.css from {url}...")
try:
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req, context=ctx) as response:
        print(f"Status: {response.status}")
        css = response.read().decode('utf-8', errors='ignore')
        print(f"Content Length: {len(css)}")
        print("CSS Content:")
        print(css[:2000])
        if len(css) > 2000:
            print("...[TRUNCATED]...")
except Exception as e:
    print(f"Error: {e}")
