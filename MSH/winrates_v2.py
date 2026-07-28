import json
import os
import csv

# --- CONFIGURATION ---
INPUT_JSON = "updated_pools.json"
OUTPUT_CSV = "card_post_acquisition_stats.csv"

# BAYESIAN SMOOTHING CONFIGURATION
# Inserts "pseudo-matches" to pull low-sample anomalies down toward a 50% average.
SMOOTHING_MATCHES = 100  
GLOBAL_BASELINE_WINRATE = 0.50  # 50% baseline anchor
# ---------------------

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

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        pools_data = json.load(f)

    # Dictionary layout: { "Card Name (Copy X)": {"wins": X, "losses": Y, "pools_opened_in": Z, "total_post_matches": W} }
    card_performance = {}
    
    pack_order = ["STARTING POOL", "PACK 1", "PACK 2", "PACK 3", "PACK 4", "PACK 5", "PACK 6", "PACK 7", "PACK 8", "PACK 9", "PACK 10", "PACK 11"]

    print(f"Executing Bayesian Smoothing calculation (pseudo-match anchor: {SMOOTHING_MATCHES})...")

    for player_name, profile in pools_data.items():
        final_wins = profile.get("wins", 0)
        final_losses = profile.get("losses", 0)
        pools = profile.get("pools", {})
        
        if not pools:
            continue

        player_card_global_counts = {}
        player_copy_milestones = {}

        # 1. Map duplicate copy chronology across the left-to-right grid layout
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
                pack_card_counts[card] = pack_card_counts.get(card, 0) + 1

            for card, count_in_this_pack in pack_card_counts.items():
                current_global_seen = player_card_global_counts.get(card, 0)
                
                for i in range(1, count_in_this_pack + 1):
                    copy_number = current_global_seen + i
                    copy_unique_key = f"{card} (Copy {copy_number})"
                    player_copy_milestones[copy_unique_key] = (w_at_receipt, l_at_receipt)
                
                player_card_global_counts[card] = current_global_seen + count_in_this_pack

        # 2. Subtract milestones from final outcomes to find performance since acquisition
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

    # 3. Compute Bayesian Statistics over the collected metrics
    final_rankings = []
    pseudo_wins_added = SMOOTHING_MATCHES * GLOBAL_BASELINE_WINRATE

    for copy_name, stats in card_performance.items():
        real_matches = stats["total_post_matches"]
        if real_matches == 0:
            continue
            
        real_wins = stats["wins"]
        real_winrate = (real_wins / real_matches) * 100
        
        # Additive Smoothing Formula
        smoothed_winrate = ((real_wins + pseudo_wins_added) / (real_matches + SMOOTHING_MATCHES)) * 100
        
        final_rankings.append({
            "Card Name": copy_name,
            "Bayes Smoothed Winrate %": round(smoothed_winrate, 2),
            "Raw Post-Acquisition Winrate %": round(real_winrate, 2),
            "Combined Post-Acquisition Record": f"{real_wins}-{stats['losses']}",
            "Total Post Matches Tracked": real_matches,
            "Pools Opened In": stats["pools_opened_in"]
        })

    # Primary sorting sequence: descending by Bayes Smoothed metric
    sorted_rankings = sorted(final_rankings, key=lambda x: x["Bayes Smoothed Winrate %"], reverse=True)

    # 4. Print Results Table directly to your Terminal layout
    print(f"\n{'RANK':<5} | {'CARD NAME':<50} | {'BAYES WR':<10} | {'RAW WR':<10} | {'RECORD':<10} | {'POOLS'}")
    print("-" * 100)
    for rank, item in enumerate(sorted_rankings[:20], 1):
        bayes_str = f"{item['Bayes Smoothed Winrate %']}%"
        raw_str = f"{item['Raw Post-Acquisition Winrate %']}%"
        print(f"{rank:<5} | {item['Card Name']:<50} | {bayes_str:<10} | {raw_str:<10} | {item['Combined Post-Acquisition Record']:<10} | {item['Pools Opened In']}")

    # 5. Export results to your workspace directory data summary file
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

