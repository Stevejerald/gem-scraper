import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import re
import time

BASE_URL = "https://bidplus.gem.gov.in"


async def extract_total_counts(page):
    await page.goto(BASE_URL + "/all-bids", timeout=0, wait_until="networkidle")
    await asyncio.sleep(2)

    # total records
    records_el = await page.query_selector("span.pos-bottom")
    txt = await records_el.inner_text()
    total_records = int(re.search(r"of\s+(\d+)", txt).group(1))

    # total pages
    last_page_el = await page.query_selector("#light-pagination a.page-link:nth-last-child(2)")
    total_pages = int((await last_page_el.inner_text()).strip())

    return total_records, total_pages


async def jump_to_last_page(page, total_pages):
    print(f"\n🔄 Jumping to LAST PAGE ({total_pages})...")

    while True:
        # get all visible page-links
        links = await page.query_selector_all("#light-pagination a.page-link")

        last_visible = 1
        last_link = None

        for ln in links:
            tx = (await ln.inner_text()).strip()
            if tx.isdigit():
                pg = int(tx)
                if pg > last_visible:
                    last_visible = pg
                    last_link = ln

        # if last visible is final page, click it and stop
        if last_visible >= total_pages:
            print(f"➡ Clicking last visible page → {last_visible}")
            await last_link.click()
            await asyncio.sleep(2)
            break

        # otherwise click that visible page and continue
        print(f"➡ Clicking page link → {last_visible}")
        await last_link.click()
        await asyncio.sleep(2)

    return total_pages


async def scrape_single_page(page, page_no):
    print(f"\n🔍 Scraping PAGE {page_no}")

    for _ in range(5):
        await page.mouse.wheel(0, 3000)
        await asyncio.sleep(0.3)

    cards = await page.query_selector_all("div.card")
    print(f"   → Found {len(cards)} tenders")

    results = []

    for c in cards:
        bid_link = await c.query_selector(".block_header a.bid_no_hover")
        bid_no = await bid_link.inner_text() if bid_link else ""
        detail_url = BASE_URL + "/" + (await bid_link.get_attribute("href")).lstrip("/") if bid_link else ""

        item_el = await c.query_selector(".card-body .col-md-4 .row:nth-child(1) a")
        items = await item_el.inner_text() if item_el else ""

        qty_el = await c.query_selector(".card-body .col-md-4 .row:nth-child(2)")
        quantity = (await qty_el.inner_text()).replace("Quantity:", "").strip() if qty_el else ""

        dept_el = await c.query_selector(".card-body .col-md-5 .row:nth-child(2)")
        department = await dept_el.inner_text() if dept_el else ""

        start_el = await c.query_selector("span.start_date")
        start_date = await start_el.inner_text() if start_el else ""

        end_el = await c.query_selector("span.end_date")
        end_date = await end_el.inner_text() if end_el else ""

        results.append({
            "Page": page_no,
            "Bid Number": bid_no,
            "Detail URL": detail_url,
            "Items": items,
            "Quantity": quantity,
            "Department": department,
            "Start Date": start_date,
            "End Date": end_date
        })

    return results


async def scrape_reverse():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        total_records, total_pages = await extract_total_counts(page)
        print("\n---------------------------------------")
        print(f"TOTAL RECORDS: {total_records}")
        print(f"TOTAL PAGES:   {total_pages}")
        print("---------------------------------------")

        # Step 1 → Jump to LAST page using page-links + NEXT
        await jump_to_last_page(page, total_pages)

        # Step 2 → SCRAPE BACKWARD from 4246 to 2061
        start_page = total_pages
        stop_page = 2061
        curr = start_page

        all_data = []

        while curr >= stop_page:
            results = await scrape_single_page(page, curr)
            all_data.extend(results)

            # find PREV button
            prev_btn = await page.query_selector("#light-pagination span.current.prev, #light-pagination a.prev")

            if not prev_btn:
                prev_btn = await page.query_selector("#light-pagination a.prev")

            if not prev_btn:
                print("❌ No PREV button found! Stopping.")
                break

            curr -= 1
            print(f"\n⬅ Clicking PREV → Page {curr}")
            await prev_btn.click()
            await asyncio.sleep(2)

        await browser.close()
        return all_data, start_page, stop_page



# MAIN
if __name__ == "__main__":
    start = time.time()

    data, start_page, stop_page = asyncio.run(scrape_reverse())

    df = pd.DataFrame(data)
    name = f"gem_reverse_{start_page}_to_{stop_page}.csv"
    df.to_csv(name, index=False)

    print("\n---------------------------------------")
    print(f"SCRAPED RECORDS: {len(df)}")
    print("---------------------------------------")
    print(f"TIME: {round(time.time() - start, 2)} sec")
    print("Saved:", name)
