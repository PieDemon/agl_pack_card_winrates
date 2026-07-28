import json
import os
import csv

# --- CONFIGURATION ---
INPUT_JSON = "updated_pools.json"
WHITELIST_TXT = "msh_cards.txt"
OUTPUT_CSV = "msh_card_post_acquisition_stats.csv"

# BAYESIAN SMOOTHING CONFIGURATION
SMOOTHING_MATCHES = 0  
GLOBAL_BASELINE_WINRATE = 0.50  
# ---------------------

def load_msh_whitelist():
    """
    Reads msh_cards.txt line by line and returns a set of normalized card names.
    """
    if not os.path.exists(WHITELIST_TXT):
        print(f"[ CRITICAL ] Whitelist file '{WHITELIST_TXT}' not found.")
        return set()
        
    msh_set = set()
    with open(WHITELIST_TXT, "r", encoding="utf-8") as f:
        for line in f:
            clean_name = line.strip().lower()
            if clean_name:
                msh_set.add(clean_name)
                
    print(f"[ SUCCESS ] Loaded {len(msh_set)} unique card titles from '{WHITELIST_TXT}'.\n")
    return msh_set

def parse_record_str(record_str):
    if not record_str or "-" not in record_str or record_str == "Unknown":
        return None
    try:
        w, l = map(int, record_str.split('-'))
        return w, l
    except ValueError:
        return None

def main():
    if not os.path.exists(INPUT_JSON):
        print(f"[ CRITICAL ] Master database '{INPUT_JSON}' not found.")
        return

    # 1. Load your manually compiled Marvel set list
    msh_whitelist = load_msh_whitelist()
    if not msh_whitelist:
        print("[ ABORT ] Whitelist is empty or missing. Terminating.")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        pools_data = json.load(f)

    card_performance = {}
    pack_order = ["STARTING POOL", "PACK 1", "PACK 2", "PACK 3", "PACK 4", "PACK 5", "PACK 6", "PACK 7", "PACK 8", "PACK 9", "PACK 10", "PACK 11"]

    print("Filtering user pools against local whitelist and executing Bayesian Smoothing...")

    for player_name, profile in pools_data.items():
        final_wins = profile.get("wins", 0)
        final_losses = profile.get("losses", 0)
        pools = profile.get("pools", {})
        
        if not pools:
            continue

        player_card_global_counts = {}
        player_copy_milestones = {}

        for pack_label in pack_order:
            if pack_label not in pools:
                continue
                
            pack_info = pools[pack_label]
            cards = pack_info.get("cards", [])
            record_str = pack_info.get("record_at_receipt")
            
            receipt_record = parse_record_str(record_str)
            if not receipt_record:
                continue
                
            w_at_receipt, l_at_receipt = receipt_record

            pack_card_counts = {}
            for card in cards:
                # FIX: Match explicitly against your clean custom txt file entries
                if card.strip().lower() in msh_whitelist:
                    pack_card_counts[card] = pack_card_counts.get(card, 0) + 1

            for card, count_in_this_pack in pack_card_counts.items():
                current_global_seen = player_card_global_counts.get(card, 0)
                
                for i in range(1, count_in_this_pack + 1):
                    copy_number = current_global_seen + i
                    copy_unique_key = f"{card} (Copy {copy_number})"
                    player_copy_milestones[copy_unique_key] = (w_at_receipt, l_at_receipt)
                
                player_card_global_counts[card] = current_global_seen + count_in_this_pack

        for copy_key, (w_at_receipt, l_at_receipt) in player_copy_milestones.items():
            post_wins = final_wins - w_at_receipt
            post_losses = final_losses - l_at_receipt

            if post_wins < 0 or post_losses < 0:
                continue

            if copy_key not in card_performance:
                card_performance[copy_key] = {
                    "wins": 0, 
                    "losses": 0, 
                    "pools_opened_in": 0,
                    "total_post_matches": 0
                }

            card_performance[copy_key]["wins"] += post_wins
            card_performance[copy_key]["losses"] += post_losses
            card_performance[copy_key]["total_post_matches"] += (post_wins + post_losses)
            card_performance[copy_key]["pools_opened_in"] += 1

    final_rankings = []
    pseudo_wins_added = SMOOTHING_MATCHES * GLOBAL_BASELINE_WINRATE

    for copy_name, stats in card_performance.items():
        real_matches = stats["total_post_matches"]
        if real_matches == 0:
            continue
            
        real_wins = stats["wins"]
        real_winrate = (real_wins / real_matches) * 100
        
        smoothed_winrate = ((real_wins + pseudo_wins_added) / (real_matches + SMOOTHING_MATCHES)) * 100
        
        final_rankings.append({
            "Card Name": copy_name,
            "Bayes Smoothed Winrate %": round(smoothed_winrate, 2),
            "Raw Post-Acquisition Winrate %": round(real_winrate, 2),
            "Combined Post-Acquisition Record": f"{real_wins}-{stats['losses']}",
            "Total Post Matches Tracked": real_matches,
            "Pools Opened In": stats["pools_opened_in"]
        })

    sorted_rankings = sorted(final_rankings, key=lambda x: x["Bayes Smoothed Winrate %"], reverse=True)

    print(f"\n--- OFFICIAL MARVEL SUPER HEROES SCOREBOARD ---")
    print(f"{'RANK':<5} | {'CARD NAME':<45} | {'BAYES WR':<10} | {'RAW WR':<10} | {'RECORD':<10} | {'POOLS'}")
    print("-" * 95)
    for rank, item in enumerate(sorted_rankings[:25], 1):
        bayes_str = f"{item['Bayes Smoothed Winrate %']}%"
        raw_str = f"{item['Raw Post-Acquisition Winrate %']}%"
        print(f"{rank:<5} | {item['Card Name']:<45} | {bayes_str:<10} | {raw_str:<10} | {item['Combined Post-Acquisition Record']:<10} | {item['Pools Opened In']}")

    with open(OUTPUT_CSV, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Card Name", "Bayes Smoothed Winrate %", "Raw Post-Acquisition Winrate %", 
            "Combined Post-Acquisition Record", "Total Post Matches Tracked", "Pools Opened In"
        ])
        writer.writeheader()
        writer.writerows(sorted_rankings)

    print(f"\n[ COMPLETE ] Bayesian analysis compiled cleanly into '{OUTPUT_CSV}'")

if __name__ == "__main__":
    main()

