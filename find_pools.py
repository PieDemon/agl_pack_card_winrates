import asyncio
import csv
import os
import sys
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
DEFAULT_TARGET_CARD = "Ragavan, Nimble Pilferer"  # Fallback if no argument is passed
MAX_CONCURRENT_WORKERS = 5                        # Adjust based on your CPU/RAM (5-10 is a good sweet spot)
INPUT_CSV = "urls.csv"
OUTPUT_CSV = "matching_pools.csv"
# ---------------------

def get_target_card():
    """
    Reads the target card name from the command line arguments.
    Falls back to the default if none is provided.
    """
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:]).strip()
    return DEFAULT_TARGET_CARD


def initialize_output_file(headers):
    """
    Creates the output CSV with headers matching the input file + the match tracking column.
    """
    if not os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers + ["Target Card Found"])


async def check_single_pool(browser, row_data, target_card, progress_lock):
    """
    Launches an isolated page context, scrapes it, and appends the player row to the CSV if it matches.
    """
    url_key = next((k for k in row_data.keys() if k and 'pool' in k.lower()), None)
    
    if not url_key or not row_data[url_key]:
        print(f"[ ERROR ] No valid URL found in row data: {row_data}")
        return

    url = row_data[url_key].strip()
    target_lower = target_card.strip().lower()
    
    context = await browser.new_context()
    page = await context.new_page()
    
    try:
        await page.goto(url, timeout=30000)
        await page.wait_for_selector(".card-node, .deck-builder, img", timeout=120000)
        
        card_elements = await page.query_selector_all("img")
        
        is_match = False
        for card in card_elements:
            alt_text = await card.get_attribute("alt")
            if alt_text and alt_text.strip().lower() == target_lower:
                is_match = True
                break
                
        if is_match:
            async with progress_lock:
                player = row_data.get("Player Name", "Unknown Player")
                print(f"[ MATCH ] -> Found in pool for {player}! Logging row...")
                
                with open(OUTPUT_CSV, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(list(row_data.values()) + [target_card])
        else:
            print(f"[  NO   ] {url}")
            
    except Exception as e:
        print(f"[ ERROR ] Could not resolve {url}: {e}")
        
    finally:
        await context.close()


async def worker(queue, browser, target_card, progress_lock):
    """
    Worker loop that pulls rows from the shared queue until it's empty.
    """
    while True:
        try:
            row_data = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        await check_single_pool(browser, row_data, target_card, progress_lock)
        queue.task_done()


async def main():
    if not os.path.exists(INPUT_CSV):
        print(f"[ CRITICAL ] The file '{INPUT_CSV}' was not found. Please create it first.")
        return

    target_card = get_target_card()
    rows_to_scan = []
    headers = []
    
    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            if any(row.values()):
                rows_to_scan.append(row)

    if not rows_to_scan:
        print(f"[ ABORT ] No valid rows found in '{INPUT_CSV}'.")
        return

    initialize_output_file(headers)

    print(f"Initializing scraping engine...")
    print(f"Target card: '{target_card}'")
    print(f"Loaded {len(rows_to_scan)} player records from '{INPUT_CSV}'")
    print(f"Concurrency profile set to {MAX_CONCURRENT_WORKERS} simultaneous workers.\n")
    
    queue = asyncio.Queue()
    for row in rows_to_scan:
        await queue.put(row)
        
    progress_lock = asyncio.Lock()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        workers = [
            asyncio.create_task(worker(queue, browser, target_card, progress_lock))
            for _ in range(MAX_CONCURRENT_WORKERS)
        ]
        
        await queue.join()
        
        for w in workers:
            w.cancel()
            
        await browser.close()
        
    print(f"\nExecution finished. Matching logs are compiled into '{OUTPUT_CSV}'.")


if __name__ == "__main__":
    asyncio.run(main())

