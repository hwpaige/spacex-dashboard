import requests, json

headers={'Authorization': 'Token 9b91363961799d7f79aabe547ed0f7be914664dd'}
r = requests.get('https://ll.thespacedevs.com/2.3.0/launches/upcoming/?limit=1&mode=normal', headers=headers)
data = r.json()['results'][0]

def walk(obj, path=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if 'landing' in k.lower() or 'location' in k.lower():
                print(f'{path}{k}: {v}')
            walk(v, path + k + ' -> ')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, path + f'[{i}] -> ')

walk(data)
