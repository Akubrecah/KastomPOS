import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    "https://demo1.jipos.co/",
    "https://demo1.jipos.co/sys/index",
    "https://demo1.jipos.co/sys/login",
    "https://demo1.jipos.co/login"
]

for url in urls:
    print(f"\nFetching {url}...")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, context=ctx) as response:
            print(f"Status: {response.status}")
            print(f"URL: {response.geturl()}")
            html = response.read()
            print(f"Content Length: {len(html)}")
            if len(html) > 0:
                print(f"HTML starts with: {html[:300].decode('utf-8', errors='ignore')!r}")
    except Exception as e:
        print(f"Error: {e}")
