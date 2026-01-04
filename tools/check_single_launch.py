import requests
import json

API_KEY = '9b91363961799d7f79aabe547ed0f7be914664dd'

def check_single_launch():
    headers = {'Authorization': f'Token {API_KEY}'}
    # Get the first upcoming launch ID
    url = "https://ll.thespacedevs.com/2.3.0/launches/upcoming/?limit=1"
    res = requests.get(url, headers=headers)
    launch_id = res.json()['results'][0]['id']
    print(f"Checking launch ID: {launch_id}")
    
    url_detailed = f"https://ll.thespacedevs.com/2.3.0/launches/{launch_id}/?mode=detailed"
    res_det = requests.get(url_detailed, headers=headers)
    data = res_det.json()
    
    print(f"Top level keys: {list(data.keys())}")
    if 'rocket' in data:
        print(f"Rocket keys: {list(data['rocket'].keys())}")
        if 'launcher_stage' in data['rocket']:
            print(f"Launcher stage is a {type(data['rocket']['launcher_stage'])}")
            if data['rocket']['launcher_stage']:
                 print(f"First launcher stage keys: {list(data['rocket']['launcher_stage'][0].keys())}")
                 if 'landing' in data['rocket']['launcher_stage'][0]:
                     print(f"Landing info: {data['rocket']['launcher_stage'][0]['landing']}")

if __name__ == "__main__":
    check_single_launch()
