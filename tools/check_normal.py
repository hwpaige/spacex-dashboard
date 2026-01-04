import requests
import json

API_KEY = '9b91363961799d7f79aabe547ed0f7be914664dd'

def check_normal_mode():
    headers = {'Authorization': f'Token {API_KEY}'}
    url = "https://ll.thespacedevs.com/2.3.0/launches/upcoming/?limit=2&mode=normal"
    res = requests.get(url, headers=headers)
    data = res.json()
    
    for i, launch in enumerate(data['results']):
        print(f"\nLaunch {i}: {launch['name']}")
        rocket = launch.get('rocket', {})
        print(f"  Rocket keys: {list(rocket.keys())}")
        if 'launcher_stage' in rocket:
            print(f"  Launcher stage found! Count: {len(rocket['launcher_stage'])}")
        else:
            print("  Launcher stage NOT found in rocket object.")

if __name__ == "__main__":
    check_normal_mode()
