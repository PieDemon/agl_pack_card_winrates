first step, manually download one of the leaderboard google spreadsheets into a file like sos.xlsx. i had to do some manual stuff to that to get it in a good format. specifically the "pack 1" column of the pools tab isn't usable by default.

then run generate_json.py to create the json skeleton with all the pack url's

then run scrape_pools.py to download all the card data. patch_pools.py was a temporary fix for an earlier bug, shouldn't be necessary anymore just kept for posterity.

then run winrates_sos.py to calculate winrates. winrates_sos_v1.py was an older version of the script.
