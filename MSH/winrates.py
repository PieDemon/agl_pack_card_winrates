import json
import os
import csv

# --- CONFIGURATION ---
INPUT_JSON = "updated_pools.json"
MIN_SAMPLE_SIZE_MATCHES = 15  # Filters out rare cards with low data sizes
OUTPUT_CSV = "card_post_acquisition_stats.csv"
# ---------------------

def parse_record_str(record_str):
    """Safely converts a 'W-L' string into integers (wins, losses)."""
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

    # Dictionary format: { "Card Name": {"wins": X, "losses": Y, "pools_opened_in": Z} }
    card_performance = {}

    print("Calculating post-acquisition card winrates via records subtraction...")

    for player_name, profile in pools_data.items():
        final_wins = profile.get("wins", 0)
        final_losses = profile.get("losses", 0)
        pools = profile.get("pools", {})
        
        if not pools:
            continue

        # Step 1: Find the absolute earliest record at which the player obtained each card
        card_earliest_receipt_record = {}

        for pack_label, pack_info in pools.items():
            cards = pack_info.get("cards", [])
            record_str = pack_info.get("record_at_receipt")
            
            receipt_record = parse_record_str(record_str)
            if not receipt_record:
                continue  # Skip packs with malformed or unknown records
                
            w_at_receipt, l_at_receipt = receipt_record

            for card in cards:
                if card not in card_earliest_receipt_record:
                    card_earliest_receipt_record[card] = (w_at_receipt, l_at_receipt)
                else:
                    current_w, current_l = card_earliest_receipt_record[card]
                    if (w_at_receipt + l_at_receipt) < (current_w + current_l):
                        card_earliest_receipt_record[card] = (w_at_receipt, l_at_receipt)

        # Step 2: Subtract receipt record from final record to find performance since acquisition
        for card, (w_at_receipt, l_at_receipt) in card_earliest_receipt_record.items():
            post_wins = final_wins - w_at_receipt
            post_losses = final_losses - l_at_receipt

            if post_wins < 0 or post_losses < 0:
                continue

            if card not in card_performance:
                card_performance[card] = {"wins": 0, "losses": 0, "pools_opened_in": 0}

            card_performance[card]["wins"] += post_wins
            card_performance[card]["losses"] += post_losses
            card_performance[card]["pools_opened_in"] += 1

    # Step 3: Compute final percentages and sort data
    final_rankings = []
    for card_name, stats in card_performance.items():
        total_matches = stats["wins"] + stats["losses"]
        winrate = (stats["wins"] / total_matches * 100) if total_matches > 0 else 0.0
        
        final_rankings.append({
            "Card Name": card_name,
            "Post-Acquisition Winrate": round(winrate, 2),
            "Post-Acquisition Record": f"{stats['wins']}-{stats['losses']}",
            "Total Post-Acquisition Matches": total_matches,
            "Pools Opened In": stats["pools_opened_in"]
        })

    # Filter out low sample sizes and sort descending by highest winrate percentage
    filtered_rankings = [c for c in final_rankings if c["Total Post-Acquisition Matches"] >= MIN_SAMPLE_SIZE_MATCHES]
    sorted_rankings = sorted(filtered_rankings, key=lambda x: x["Post-Acquisition Winrate"], reverse=True)

    # Step 4: Output table block directly to terminal console layout
    print(f"\n{'RANK':<5} | {'CARD NAME':<35} | {'WINRATE':<8} | {'MATCHES':<8} | {'COMBINED RECORD'}")
    print("-" * 75)
    for rank, item in enumerate(sorted_rankings[:20], 1):
        # Cleaned formatting string parameter inputs
        winrate_str = f"{item['Post-Acquisition Winrate']}%"
        print(f"{rank:<5} | {item['Card Name']:<35} | {winrate_str:<8} | {item['Total Post-Acquisition Matches']:<8} | {item['Post-Acquisition Record']}")

    # Step 5: Export directly to CSV file
    with open(OUTPUT_CSV, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Card Name", "Post-Acquisition Winrate", "Post-Acquisition Record", "Total Post-Acquisition Matches", "Pools Opened In"])
        writer.writeheader()
        writer.writerows(sorted_rankings)

    print(f"\n[ COMPLETE ] Subtraction analysis done. Detailed stats exported to: '{OUTPUT_CSV}'")

if __name__ == "__main__":
    main()

