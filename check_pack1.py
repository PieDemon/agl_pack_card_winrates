import json

with open("downloaded_pools.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Pick the first player name in the dictionary to look at their keys
first_player = list(data.keys())[0]
print(f"Keys found for {first_player}: {list(data[first_player]['pools'].keys())}")

