import requests
import json

API_KEY = '9b91363961799d7f79aabe547ed0f7be914664dd'
api_url_list = "https://ll.thespacedevs.com/2.3.0/launches/upcoming/?mode=list&limit=1"
api_url_normal = "https://ll.thespacedevs.com/2.3.0/launches/upcoming/?mode=normal&limit=1"
api_url_detailed = "https://ll.thespacedevs.com/2.3.0/launches/upcoming/?mode=detailed&limit=1"

def run_api_check():
    def find_landing_info(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if "landing" in k.lower() or "location" in k.lower() or "expendable" in k.lower():
                    print(f"Found potential landing key '{prefix}{k}': {v}")
                find_landing_info(v, prefix + k + " -> ")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                find_landing_info(item, prefix + f"[{i}] -> ")

    try:
        headers = {'Authorization': f'Token {API_KEY}'}
        
        print("--- Fetching LIST mode data ---")
        response_list = requests.get(api_url_list, headers=headers, timeout=10)
        response_list.raise_for_status()
        data_list = response_list.json()
        print(f"List mode first result keys: {list(data_list['results'][0].keys()) if data_list['results'] else 'No results'}")

        print("\n--- Fetching NORMAL mode data ---")
        response_normal = requests.get(api_url_normal, headers=headers, timeout=10)
        response_normal.raise_for_status()
        data_normal = response_normal.json()
        print(f"Normal mode first result keys: {list(data_normal['results'][0].keys()) if data_normal['results'] else 'No results'}")
        if data_normal['results']:
            res = data_normal['results'][0]
            print(f"Rocket: {res.get('rocket', {}).get('configuration', {}).get('name')}")
            print(f"Orbit: {res.get('mission', {}).get('orbit', {}).get('name')}")
            print(f"Pad: {res.get('pad', {}).get('name')}")
            print("Searching for landing info in NORMAL mode:")
            find_landing_info(res)

        print("\n--- Fetching DETAILED mode data ---")
        response_detailed = requests.get(api_url_detailed, headers=headers, timeout=10)
        response_detailed.raise_for_status()
        data_detailed = response_detailed.json()
        print(f"Detailed mode first result keys: {list(data_detailed['results'][0].keys()) if data_detailed['results'] else 'No results'}")
        # print(json.dumps(data_detailed, indent=4)) # Uncomment to see full detailed data

        print("\n--- Comparing first result ---")
        if data_list['results'] and data_detailed['results']:
            list_keys = set(data_list['results'][0].keys())
            detailed_keys = set(data_detailed['results'][0].keys())
            
            only_in_detailed = detailed_keys - list_keys
            print(f"Keys only in DETAILED: {only_in_detailed}")
            
            # Specifically check for landing info
            print("\n--- Checking for Landing Info ---")
            detailed_launch = data_detailed['results'][0]
            list_launch = data_list['results'][0]
            

            print("Searching in LIST mode:")
            find_landing_info(list_launch)
            
            print("\nSearching in DETAILED mode:")
            find_landing_info(detailed_launch)

        print("\nAll checks completed.")

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except AssertionError as e:
        print(f"Assertion failed: {e}")

if __name__ == "__main__":
    run_api_check()