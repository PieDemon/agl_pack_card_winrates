import json
import os
import re
import csv

# --- CONFIGURATION ---
INPUT_JSON = "updated_pools.json"
INPUT_CSV = "pool_changes.csv"
OUTPUT_JSON = "final_pools.json"
# ---------------------

def clean_player_name(raw_name):
    """
    Cleans a string name (e.g., 'Zeke W - smarmyplatapus#30066') 
    down to the short name style used in the JSON keys ('Zeke W').
    """
    if not raw_name:
        return ""
    name_str = str(raw_name).strip()
    if " - " in name_str:
        return name_str.split(" - ")[0].strip()
    if "-" in name_str:
        return name_str.split("-")[0].strip()
    return name_str

def extract_set_code(comment_str):
    """
    Extracts the 3-letter alphanumeric set code from formatting phrases like:
    'Origin: otj (-2)' -> 'otj' or 'Comeback: msh (±0)' -> 'msh'
    """
    comment_clean = str(comment_str).strip()
    if comment_clean == "MSH pool":
        return None
        
    # Searches for 'Origin:' or 'Comeback:' followed by any 3-letter alphanumeric code
    match = re.search(r'(?:Origin|Comeback):\s*([a-zA-Z0-9]{3})', comment_clean, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None

def main():
    if not os.path.exists(INPUT_JSON):
        print(f"[ CRITICAL ] Master database file '{INPUT_JSON}' not found.")
        return
        
    if not os.path.exists(INPUT_CSV):
        print(f"[ CRITICAL ] Timeline log file '{INPUT_CSV}' not found.")
        return

    # Load your current baseline JSON tracking data
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        pools_data = json.load(f)

    # Dictionary layout to track row frequencies: { "Cleaned Name": [ "otj", "msh", "mkm" ] }
    player_pack_sets_timeline = {}

    print(f"Parsing '{INPUT_CSV}' chronologically to map set origins...")
    
    # Open CSV layout securely tracking potential byte-order marks
    with open(INPUT_CSV, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            raw_name = row.get("Name")
            comment = row.get("Comment")
            
            if not raw_name or not comment:
                continue
                
            # Filter administrative setups
            if str(comment).strip() == "MSH pool":
                continue
                
            set_code = extract_set_code(comment)
            if not set_code:
                continue
                
            clean_name = clean_player_name(raw_name)
            
            if clean_name not in player_pack_sets_timeline:
                player_pack_sets_timeline[clean_name] = []
                
            # Add to the chronological list for this specific player profile
            player_pack_sets_timeline[clean_name].append(set_code)

    print("Injecting set identifiers back into JSON pack configurations...")
    updated_packs_count = 0

    # Cross-reference back into your json layout dictionary keys
    for json_player_name, profile in pools_data.items():
        clean_json_name = json_player_name.strip().lower()
        
        # Pull corresponding timeline index array
        matched_timeline_key = next((k for k in player_pack_sets_timeline.keys() if k.strip().lower() == clean_json_name), None)
        
        if not matched_timeline_key:
            continue
            
        set_code_list = player_pack_sets_timeline[matched_timeline_key]
        pools = profile.get("pools", {})
        
        # Explicit sequential array of dynamic comeback packs
        ordered_comeback_labels = ["PACK 1", "PACK 2", "PACK 3", "PACK 4", "PACK 5", "PACK 6", "PACK 7", "PACK 8", "PACK 9", "PACK 10", "PACK 11"]
        
        # Match chronology index offsets 1:1
        for idx, pack_label in enumerate(ordered_comeback_labels):
            if pack_label in pools:
                if idx < len(set_code_list):
                    target_set = set_code_list[idx]
                    
                    # Store set info directly in the pack dictionary wrapper
                    pools[pack_label]["set"] = target_set
                    updated_packs_count += 1

    # Write data cleanly back out to a fresh final output file
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(pools_data, f, indent=2)

    print(f"\n[ COMPLETE ] Successfully injected '{updated_packs_count}' set properties.")
    print(f"Your fully enriched database has been compiled into: '{OUTPUT_JSON}'")

if __name__ == "__main__":
    main()

