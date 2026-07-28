import asyncio
import json
import os
import sys
from playwright.async_api import async_playwright

# --- CONFIGURATION DEFAULT ---
DEFAULT_INPUT_JSON = "./SOS/sos_pools.json"
MAX_CONCURRENT_WORKERS = 5  # Runs 5 browser streams in parallel for high performance
# -----------------------------

def get_target_json_path():
    """Reads target JSON path from command line or falls back to default."""
    if len(sys.argv) > 1:
        return sys.argv[1].strip()
    return DEFAULT_INPUT_JSON

def load_database(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"[ ERROR ] '{path}' contains malformed JSON.")
                return {}
    return {}

def save_database(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

async def scrape_single_pool(browser, player_key, pack_label, url, progress_lock, db_data, json_path):
    """
    Launches an isolated headless browser tab, waits for cards to render, 
    and saves the extracted array directly back into the main JSON database.
    """
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    try:
        print(f"[ LOADING ] {player_key} -> {pack_label}")
        
        # Navigate and wait for the framework to completely load assets
        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
        
        # Wait up to 30 seconds for the React app container nodes to mount visually
        await page.wait_for_selector("#root, .deck-builder, .app", timeout=30000)
        
        # Give the React state tree 1.5 seconds to populate the card image grids completely
        await asyncio.sleep(1.5)
        
        # Pull all images on the page
        img_elements = await page.query_selector_all("img")
        
        cards_found = []
        for img in img_elements:
            alt_text = await img.get_attribute("alt")
            if alt_text:
                clean_text = alt_text.strip()
                # Safely skip infrastructure or donation assets
                if (clean_text and 
                    "patreon" not in clean_text.lower() and 
                    "ko-fi" not in clean_text.lower() and
                    "logo" not in clean_text.lower() and
                    "banner" not in clean_text.lower()):
                    cards_found.append(clean_text)
                    
        if cards_found:
            # Use async lock to ensure safe parallel file modifications
            async with progress_lock:
                db_data[player_key]["pools"][pack_label]["cards"] = cards_found
                print(f"[ SUCCESS ] Scraped {len(cards_found)} cards into {pack_label} for {player_key}")
                save_database(json_path, db_data)
        else:
            print(f"[ WARNING ] React container loaded, but 0 cards found for {player_key} -> {pack_label}")
            
    except Exception as e:
        print(f"[ ERROR ] Failure resolving {pack_label} for {player_key}: {e}")
    finally:
        await context.close()

async def worker(queue, browser, progress_lock, db_data, json_path):
    while True:
        try:
            task = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        await scrape_single_pool(
            browser, 
            task["player_key"], 
            task["pack_label"], 
            task["url"], 
            progress_lock, 
            db_data, 
            json_path
        )
        queue.task_done()

async def main():
    json_path = get_target_json_path()
    db_data = load_database(json_path)
    
    if not db_data:
        print(f"[ CRITICAL ] Target JSON database file '{json_path}' is empty or missing.")
        return

    # Build queue of missing pack items
    queue = asyncio.Queue()
    for player_name, profile in db_data.items():
        pools = profile.get("pools", {})
        for pack_label, pack_info in pools.items():
            # If 'cards' array is completely empty, it means we haven't scraped it yet
            if not pack_info.get("cards"):
                await queue.put({
                    "player_key": player_name,
                    "pack_label": pack_label,
                    "url": pack_info["url"]
                })

    if queue.qsize() == 0:
        print(f"\n[ INFO ] All pack items inside '{json_path}' are already fully scraped and cached!")
        return

    print(f"Initializing headless scraping engine. Concurrency level: {MAX_CONCURRENT_WORKERS} workers.")
    print(f"Queueing {queue.qsize()} missing pools for automated download chunks...\n")
    
    progress_lock = asyncio.Lock()
    
    async with async_playwright() as p:
        # Launching with headless=True for maximum execution speed
        browser = await p.chromium.launch(headless=True)
        
        # Fire up parallel workers to consume the queue concurrently
        workers = [
            asyncio.create_task(worker(queue, browser, progress_lock, db_data, json_path))
            for _ in range(MAX_CONCURRENT_WORKERS)
        ]
        
        await queue.join()
        for w in workers:
            w.cancel()
        await browser.close()
        
    print(f"\n[ COMPLETE ] All available card lists downloaded successfully into '{json_path}'.")

if __name__ == "__main__":
    asyncio.run(main())

