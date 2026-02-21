import urllib.request
import json
import traceback

url = "http://localhost:5501/api/kr/reanalyze/gemini"
data = json.dumps({"force": True}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    response = urllib.request.urlopen(req)
    print("Response Status:", response.status)
    print("Response Body:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError Status:", e.code)
    print("Error Body:", e.read().decode('utf-8'))
except Exception as e:
    print("Other Exception:", str(e))
    traceback.print_exc()
