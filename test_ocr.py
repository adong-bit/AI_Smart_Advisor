import requests

url = "http://localhost:5008/api/portfolio-ocr-import"
files = {'file': open('/Users/ohmygodcurry/.cursor/projects/Users-ohmygodcurry-Desktop/assets/IMG_7288-c49a0a9f-4288-4fff-a344-d7718962c59a.png', 'rb')}
res = requests.post(url, files=files)
print(res.json())
