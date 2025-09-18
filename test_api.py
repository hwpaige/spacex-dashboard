import requests
import json
from datetime import datetime
import pytz

current_year = datetime.now(pytz.UTC).year
url = f'https://ll.thespacedevs.com/2.0.0/launch/previous/?lsp__name=SpaceX&net__gte={current_year}-01-01&net__lte={current_year}-12-31&limit=100'
print(f'Fetching from: {url}')
response = requests.get(url, timeout=10)
print(f'Status: {response.status_code}')
data = response.json()
print(f'Data: {data}')
