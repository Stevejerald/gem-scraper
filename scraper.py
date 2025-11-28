# scraper.py
import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import time
import re

PROGRESS = {"current": 0, "total": 0, "message": "Not started"}

BASE_URL = "https://bidplus.gem.gov.in"

async def apply_sorting(page):
    PROGRESS["message"] = "Applying sorting..."
    dropdown_btn = await page.query_selector("#currentSort")
    await dropdown_btn.click()
    await asyncio.sleep(1)

    sort_option = await page.query_selector("#Bid-Start-Date-Latest")
    if sort_option:
        await sort_option.click()
    await asyncio.sleep(2)

async def extract_total_counts(page):
    PROGRESS["message"] = "Extracting total counts..."
    await page.goto(f"{BASE_URL}/all-bids", timeout=0, wait_until="networkidle")
    await asyncio.sleep(2)

    await apply_sorting(page)

    records_el = await page.query_selector("span.pos-bottom")
    total_records = 0
    if records_el:
        text = await records_el.inner_text()
        match = re.search(r"of\s+(\d+)\s+records", text)
        if match:
            total_records = int(match.group(1))

    last_page_el = await page.query_selector("#light-pagination a.page-link:nth-last-child(2)")
    total_pages = int((await last_page_el.inner_text()).strip()) if last_page_el else 1

    PROGRESS["total"] = total_pages
    return total_records, total_pages


async def scrape_single_page(page, page_no):
    PROGRESS["current"] = page_no
    PROGRESS["message"] = f"Scraping page {page_no}..."

    cards = await page.query_selector_all("div.card")
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
    global PROGRESS
    PROGRESS["message"] = "Starting chromium..."

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer"
            ]
        )


        context = await browser.new_context()
        page = await context.new_page()

        total_records, total_pages = await extract_total_counts(page)

        all_data = []
        page_no = 1

        # First page
        page_results = await scrape_single_page(page, page_no)
        all_data.extend(page_results)

        # Loop next pages
        while True:
            next_btn = await page.query_selector("#light-pagination a.next")

            if not next_btn:
                break

            page_no += 1
            await next_btn.click()
            await asyncio.sleep(2)

            page_results = await scrape_single_page(page, page_no)
            all_data.extend(page_results)

            if page_no >= total_pages:
                break

        await browser.close()

        df = pd.DataFrame(all_data)
        df.to_csv("gem_full_fixed.csv", index=False)

        PROGRESS["message"] = "Scraping completed."

        return all_data
