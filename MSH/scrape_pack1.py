import asyncio
import json
import os
import re
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
MAX_CONCURRENT_WORKERS = 1  
COOLDOWN_SECONDS = 3.0      
INPUT_TXT = "pack_ones.txt"
DATA_CACHE_FILE = "downloaded_pools.json"
# ---------------------

def load_existing_cache():
    if os.path.exists(DATA_CACHE_FILE):
        with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_cache(cache_data):
    with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)

def parse_pack_ones_txt():
    if not os.path.exists(INPUT_TXT):
        print(f"[ CRITICAL ] The text file '{INPUT_TXT}' was not found.")
        return {}

    parsed_links = {}
    print(f"Reading target links from local file '{INPUT_TXT}'...")
    
    with open(INPUT_TXT, "r", encoding="utf-8") as f:
        for line in f:
            clean_line = line.strip()
            if not clean_line:
                continue
                
            match = re.match(r'^([^,\s]+(?:\s+[^,\s]+)*)[\s,]+(https?://[^\s,]+)', clean_line)
            if match:
                player_name = match.group(1).strip()
                url = match.group(2).strip()
                parsed_links[player_name] = url
            else:
                parts = clean_line.split(',')
                if len(parts) >= 2 and parts[-1].strip().startswith("http"):
                    player_name = ",".join(parts[:-1]).strip()
                    url = parts[-1].strip()
                    parsed_links[player_name] = url

    print(f"[ INFO ] Successfully parsed {len(parsed_links)} target records.")
    return parsed_links

async def scrape_pack_one_url(browser, json_player_key, url, progress_lock, cache_data):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1440, "height": 900}
    )
    page = await context.new_page()
    
    try:
        print(f"[ LOADING ] Processing {json_player_key} -> {url}")
        
        # Load page content layout
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        
        # FIX: Wait for the main web app wrapper grid to exist instead of specific image paths
        await page.wait_for_selector("#root, .deck-builder, .app", timeout=30000)
        
        # Give the JavaScript app a stable 3 seconds to fully populate the card components visually
        print(f"[ WAITING ] Giving the page layout a moment to finish drawing cards...")
        await asyncio.sleep(3.0)
        
        # Pull all imagery tags on the entire page
        card_elements = await page.query_selector_all("img")
        
        cards_found = []
        for card in card_elements:
            alt_text = await card.get_attribute("alt")
            if alt_text:
                clean_text = alt_text.strip()
                # Exclude administrative UI, donation tools, and system backgrounds
                if (clean_text and 
                    "patreon" not in clean_text.lower() and 
                    "ko-fi" not in clean_text.lower() and
                    "logo" not in clean_text.lower() and
                    "banner" not in clean_text.lower()):
                    cards_found.append(clean_text)
                
        if cards_found:
            async with progress_lock:
                cache_data[json_player_key]["pools"]["PACK 1"] = {
                    "url": url,
                    "cards": cards_found
                }
                print(f"[ SUCCESS ] Scraped {len(cards_found)} cards into 'PACK 1' for {json_player_key}")
                save_cache(cache_data)
        else:
            print(f"[ WARNING ] React container loaded, but zero card images were detected for {json_player_key}")
            
    except Exception as e:
        print(f"[ ERROR ] Failure scraping target URL for {json_player_key}: {e}")
    finally:
        await context.close()

async def worker(queue, browser, progress_lock, cache_data):
    while True:
        try:
            task = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        await scrape_pack_one_url(browser, task["json_key"], task["url"], progress_lock, cache_data)
        queue.task_done()
        
        if queue.qsize() > 0:
            print(f"[ PAUSE ] Waiting {COOLDOWN_SECONDS} seconds before the next request...")
            await asyncio.sleep(COOLDOWN_SECONDS)

async def main():
    cache_data = load_existing_cache()
    if not cache_data:
        print(f"[ CRITICAL ] Master file '{DATA_CACHE_FILE}' was not detected.")
        return

    txt_links = parse_pack_ones_txt()
    queue = asyncio.Queue()

    for txt_name, url in txt_links.items():
        clean_txt_name = txt_name.strip().lower()
        json_key = next((k for k in cache_data.keys() if k.strip().lower() == clean_txt_name), None)
        
        if json_key:
            pack_state = cache_data[json_key]["pools"].get("PACK 1")
            has_bad_data = False
            
            if isinstance(pack_state, dict) and "cards" in pack_state:
                has_bad_data = any("patreon" in c.lower() or "ko-fi" in c.lower() for c in pack_state["cards"]) or len(pack_state["cards"]) < 3
            elif isinstance(pack_state, list):
                has_bad_data = True

            if "PACK 1" not in cache_data[json_key]["pools"] or has_bad_data:
                await queue.put({"json_key": json_key, "url": url})

    if queue.qsize() == 0:
        print("\nAll parsed entries are fully accounted for with valid 'PACK 1' lists in your database!")
        return

    print(f"Queueing {queue.qsize()} records. Running broad app-node container listener mode.")
    progress_lock = asyncio.Lock()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        workers = [
            asyncio.create_task(worker(queue, browser, progress_lock, cache_data))
            for _ in range(MAX_CONCURRENT_WORKERS)
        ]
        await queue.join()
        for w in workers:
            w.cancel()
        await browser.close()
        
    print(f"\nTargeted recovery complete! Open '{DATA_CACHE_FILE}' to see changes.")

if __name__ == "__main__":
    asyncio.run(main())

