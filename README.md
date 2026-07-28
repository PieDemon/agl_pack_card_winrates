Useful data files:
final_pools.json - the compilation of all the packs, their contents, and related details
msh_cards, msh_commons, msh_uncommons - just handy lists for filtering cards of those types
pools.xslx - a hacked copy of the google sheet with extra stuff in it, used as the basis of most of the other data. most data is extracted elsewhere, except for match results, i think those still only exist in here
pack_ones.txt - the pack ones had a bug in the way they were exported to xslx, so to get the links i had to do it separately

Recap of my investigations today:

scrape_pack1.py was the starting point for downloading all the data from sealeddeck.tech and output downloaded_pools.json
then add_records.py was used. this took pools.xlsx and downloaded_pools.json to output updated_pools.json
later i used inject_pack_sets.py to take updated_pools.json and pool_changes.csv as in put then output final_pools.json
final_pools.json should have all the data. the rest of the scripts in here are all different ways to take the processed data and then analyze it to create different outputs. 
winrates.py was the first attempt and it gave all the winrate data of all the cards
winrates_msh.py was the next attempt, only looking at msh cards
winrates_packs.py was for looking at the pack winrates.
