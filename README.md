scrape_pack1.py was the starting point for downloading all the data from sealeddeck.tech and output downloaded_pools.json

then add_records.py was used. this took pools.xlsx and downloaded_pools.json to output updated_pools.json

later i used inject_pack_sets.py to take updated_pools.json and pool_changes.csv as in put then output final_pools.json

final_pools.json should have all the data. the rest of the scripts in here are all different ways to take the processed data and then analyze it to create different outputs. 

winrates.py was the first attempt and it gave all the winrate data of all the cards

winrates_msh.py was the next attempt, only looking at msh cards

winrates_packs.py was for looking at the pack winrates.
