import asyncio 
from playwright.async_api import async_playwright
import pandas as pd
import time
import re

BASE_URL = "https://bidplus.gem.gov.in"


async def apply_sorting(page):
    """Select 'Bid Start Date: Latest First' from the sorting dropdown."""

    print("\n🔧 Applying sort: Bid Start Date → Latest First")

    # Open dropdown
    dropdown_btn = await page.query_selector("#currentSort")
    await dropdown_btn.click()
    await asyncio.sleep(1)

    # Click the sorting option
    sort_option = await page.query_selector("#Bid-Start-Date-Latest")
    if not sort_option:
        print("❌ Sort option not found!")
    else:
        await sort_option.click()
        await asyncio.sleep(2)  # wait for reload

    print("✅ Sorting applied!\n")


async def extract_total_counts(page):
    """Extract total records + total pages from page 1."""
    await page.goto(f"{BASE_URL}/all-bids", timeout=0, wait_until="networkidle")
    await asyncio.sleep(2)

    # APPLY SORTING HERE
    await apply_sorting(page)

    # Extract total records
    records_el = await page.query_selector("span.pos-bottom")
    total_records = 0
    if records_el:
        text = await records_el.inner_text()
        match = re.search(r"of\s+(\d+)\s+records", text)
        if match:
            total_records = int(match.group(1))

    # Extract total pages
    last_page_el = await page.query_selector("#light-pagination a.page-link:nth-last-child(2)")
    total_pages = 1
    if last_page_el:
        last_page_text = (await last_page_el.inner_text()).strip()
        if last_page_text.isdigit():
            total_pages = int(last_page_text)

    return total_records, total_pages


async def scrape_single_page(page, page_no):
    """Scrape currently visible page (content already loaded)."""

    print(f"\n🔍 Scraping PAGE {page_no}")

    # Scroll to load all cards
    for _ in range(5):
        await page.mouse.wheel(0, 3000)
        await asyncio.sleep(0.3)

    cards = await page.query_selector_all("div.card")
    print(f"   → Found {len(cards)} tenders")

    results = []

    for c in cards:
        bid_link = await c.query_selector(".block_header a.bid_no_hover")
        bid_no = await bid_link.inner_text() if bid_link else ""
        detail_url = (
            BASE_URL + "/" + (await bid_link.get_attribute("href")).lstrip("/")
            if bid_link else ""
        )

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


async def scrape_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        # Get total records & pages (sorting applied inside)
        total_records, total_pages = await extract_total_counts(page)

        print("\n-------------------------------------")
        print(f"📌 TOTAL RECORDS: {total_records}")
        print(f"📌 TOTAL PAGES:   {total_pages}")
        print("-------------------------------------")
        print("🚀 Starting scraping...\n")

        all_data = []

        # Scrape page 1 manually loaded (sorted)
        page_no = 1
        page_results = await scrape_single_page(page, page_no)
        all_data.extend(page_results)

        # Now loop through remaining pages via NEXT button
        while True:
            next_btn = await page.query_selector("#light-pagination a.next")

            if not next_btn:
                print("\n✅ No more pages. Scraping completed.")
                break

            page_no += 1

            print(f"\n➡ Clicking NEXT → Page {page_no}")
            await next_btn.click()
            await asyncio.sleep(2)  # Wait JS reload

            page_results = await scrape_single_page(page, page_no)
            all_data.extend(page_results)

            if page_no >= total_pages:
                break

        await browser.close()
        return all_data, total_records, total_pages


# MAIN EXECUTION
if __name__ == "__main__":
    start = time.time()

    data, total_records, total_pages = asyncio.run(scrape_all())

    df = pd.DataFrame(data)
    df.to_csv("gem_full_fixed.csv", index=False)

    print("\n-------------------------------------")
    print(f"SCRAPED RECORDS:  {len(data)}")
    print(f"EXPECTED RECORDS: {total_records}")
    print("-------------------------------------")
    print(f"⏱ TOTAL TIME: {round(time.time() - start, 2)} seconds")
    print("📁 Saved: gem_full_fixed.csv")
