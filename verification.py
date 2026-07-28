import json
import os
import pandas as pd

INPUT_JSON = "final_pools.json"
INPUT_XLSX = "pools.xlsx"
MATCHES_SHEET = "Matches"

def clean_player_name(raw_name):
    if not raw_name or pd.isna(raw_name):
        return ""
    name_str = str(raw_name).strip()
    if " - " in name_str:
        return name_str.split(" - ")[0].strip()
    if "-" in name_str:
        return name_str.split("-")[0].strip()
    return name_str

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    json_players = json.load(f).keys()

df_matches = pd.read_excel(INPUT_XLSX, sheet_name=MATCHES_SHEET)

unmatched_winners = set()
unmatched_losers = set()
total_wins = 0
total_losses = 0

for _, row in df_matches.iterrows():
    winner = clean_player_name(row.get("Your Name", ""))
    loser = clean_player_name(row.get("Loser Name", ""))
    
    if winner in json_players:
        total_wins += 1
    else:
        unmatched_winners.add(winner)
        
    if loser in json_players:
        total_losses += 1
    else:
        unmatched_losers.add(loser)

print(f"Total rows in spreadsheet: {len(df_matches)}")
print(f"Matches accounted for in script math: {total_wins} Wins vs {total_losses} Losses")
print(f"Net Distortion Gap: {total_losses - total_wins} extra losses\n")

if unmatched_winners:
    print(f"Winners skipped (Not in JSON): {unmatched_winners}")
if unmatched_losers:
    print(f"Losers skipped (Not in JSON): {unmatched_losers}")

