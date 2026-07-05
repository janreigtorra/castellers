import asyncio
import glob
import json
import os
import re
import sys
from datetime import datetime

import nodriver as uc
import requests
from bs4 import BeautifulSoup
from nodriver.cdp import network as cdp_network
from nodriver.cdp.network import CookieSameSite

BASE_URL = "https://castellscat.cat/ca/base-de-dades"

MAX_PAGES = 1000
OUTPUT_FORMAT = "json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data_basic", "castellers_data.json"))

PAGE_READY_TIMEOUT = 120
TURNSTILE_TIMEOUT = 90
RESULTS_TIMEOUT = 90
PAGINATION_TIMEOUT = 60

DATE_START = sys.argv[1] if len(sys.argv) >= 3 else None
DATE_END = sys.argv[2] if len(sys.argv) >= 3 else None


def parse_date_location(date_location_text):
    text = date_location_text.replace("\n", " ").strip()

    date_match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    date = date_match.group(1) if date_match else None

    time_match = re.search(r"(\d{1,2}:\d{2})", text)
    time = time_match.group(1) if time_match else None

    if time_match:
        location_part = text[time_match.end() :].strip()
    elif date_match:
        location_part = text[date_match.end() :].strip()
    else:
        location_part = text

    city_start_index = None
    for i in range(len(location_part) - 1):
        if location_part[i].islower() and location_part[i + 1].isupper():
            city_start_index = i + 1
            break

    if city_start_index is not None:
        place = location_part[:city_start_index].strip()
        city = location_part[city_start_index:].strip()
    else:
        place = ""
        city = location_part

    return {
        "date": date,
        "time": time,
        "place": place,
        "city": city,
        "raw_text": date_location_text,
    }


def parse_castell_result(result_text):
    text = result_text.strip()
    status_match = re.search(r"\(([^)]+)\)", text)
    status = status_match.group(1) if status_match else None
    castell_name = text[: status_match.start()].strip() if status_match else text

    return {
        "castell_name": castell_name,
        "status": status,
        "raw_text": result_text,
    }


def clean_event_name(event_name):
    if not event_name:
        return event_name

    match = re.search(r"[a-z]([A-Z].*)", event_name)
    return match.group(1) if match else event_name


def event_key(event):
    return (
        event.get("date", ""),
        event.get("event_name", ""),
        event.get("city", ""),
        event.get("time", ""),
    )


def resolve_browser_executable():
    configured = os.environ.get("CHROME_EXECUTABLE_PATH")
    playwright_bins = glob.glob(
        "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome"
    ) + glob.glob("/ms-playwright/chromium-*/chrome-linux/chrome")
    system_bins = [
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    candidates = ([configured] if configured else []) + playwright_bins + system_bins
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def fetch_flaresolverr_cookies(url):
    flaresolverr_url = os.environ.get("FLARESOLVERR_URL", "").rstrip("/")
    if not flaresolverr_url:
        return None, ""

    api_url = f"{flaresolverr_url}/v1"
    session_id = None
    try:
        response = requests.post(
            api_url,
            json={"cmd": "sessions.create"},
            timeout=30,
        )
        response.raise_for_status()
        session_id = response.json()["session"]

        response = requests.post(
            api_url,
            json={
                "cmd": "request.get",
                "url": url,
                "session": session_id,
                "maxTimeout": 120000,
            },
            timeout=130,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "ok":
            raise RuntimeError(payload.get("message", "FlareSolverr request failed"))

        solution = payload["solution"]
        print(
            "FlareSolverr bypassed Cloudflare challenge "
            f"(HTTP {solution.get('status')})"
        )
        return solution.get("cookies", []), solution.get("userAgent", "")
    except requests.RequestException as exc:
        print(f"FlareSolverr unavailable, continuing without it: {exc}")
        return None, ""
    finally:
        if session_id:
            try:
                requests.post(
                    api_url,
                    json={"cmd": "sessions.destroy", "session": session_id},
                    timeout=10,
                )
            except requests.RequestException:
                pass


async def apply_cookies(page, cookies):
    same_site_map = {
        "Strict": CookieSameSite.STRICT,
        "Lax": CookieSameSite.LAX,
        "None": CookieSameSite.NONE,
    }

    for cookie in cookies:
        params = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie.get("domain") or ".castellscat.cat",
            "path": cookie.get("path") or "/",
            "secure": bool(cookie.get("secure", False)),
            "http_only": bool(cookie.get("httpOnly", False)),
        }
        same_site = cookie.get("sameSite")
        if same_site in same_site_map:
            params["same_site"] = same_site_map[same_site]
        await page.send(cdp_network.set_cookie(**params))


def load_existing_events(file_path):
    if os.path.exists(file_path):
        print(f"Loading existing events from {file_path}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)

            existing_events = existing_data.get("events", [])
            existing_metadata = existing_data.get("metadata", {})
            print(f"Found {len(existing_events)} existing events")
            return existing_events, existing_metadata
        except Exception as e:
            print(f"Error loading existing file: {e}")
            print("Starting fresh...")
            return [], {}

    print(f"File {file_path} does not exist. Starting fresh...")
    return [], {}


async def wait_for_page_ready(page):
    for i in range(PAGE_READY_TIMEOUT):
        title = await page.evaluate("document.title")
        if title and "Just a moment" not in title and "Base de dades" in title:
            print(f"Page ready after {i}s: {title}")
            return
        await asyncio.sleep(1)

    title = await page.evaluate("document.title")
    raise RuntimeError(
        f"Timed out waiting for castellscat.cat to load (Cloudflare challenge). Last title: {title!r}"
    )


async def wait_for_turnstile(page):
    await page.evaluate(
        'document.querySelector("#form-search")?.scrollIntoView({block: "center"})'
    )
    await asyncio.sleep(2)

    for attempt in range(3):
        try:
            turnstile = await page.select(".cf-turnstile")
            if turnstile:
                await turnstile.click()
                print(f"Clicked Turnstile widget (attempt {attempt + 1})")
        except Exception as exc:
            print(f"Turnstile click attempt {attempt + 1} skipped: {exc}")

        for i in range(TURNSTILE_TIMEOUT):
            token = await page.evaluate(
                'document.querySelector(\'input[name="cf-turnstile-response"]\')?.value || ""'
            )
            if token:
                print(f"Turnstile ready after {i}s (attempt {attempt + 1})")
                return
            await asyncio.sleep(1)

        await asyncio.sleep(2)

    raise RuntimeError(
        "Timed out waiting for Cloudflare Turnstile on the search form. "
        "Try running again with SCRAPER_HEADLESS=false and complete any "
        "verification shown in the browser window."
    )


async def submit_search(page, date_start, date_end):
    date_start_js = json.dumps(date_start)
    date_end_js = json.dumps(date_end)
    await page.evaluate(f'document.querySelector("#date_start").value = {date_start_js}')
    await page.evaluate(f'document.querySelector("#date_end").value = {date_end_js}')
    await asyncio.sleep(0.5)
    await page.evaluate('document.querySelector("#send-search").click()')
    print(f"Submitted search: {date_start} to {date_end}")


async def wait_for_results(page):
    for i in range(RESULTS_TIMEOUT):
        count = await page.evaluate('document.querySelectorAll("ul.resultats").length')
        if count > 0:
            print(f"Results visible after {i}s ({count} events on page)")
            return count
        await asyncio.sleep(1)

    count = await page.evaluate('document.querySelectorAll("ul.resultats").length')
    if count == 0:
        html = await page.get_content()
        if "No s'han trobat" in html or "no s'han trobat" in html.lower():
            print("Search returned no results for this date range")
            return 0
        raise RuntimeError(
            "Timed out waiting for search results. "
            "The form may have been rejected by Cloudflare Turnstile."
        )
    return count


async def wait_for_page_change(page, previous_html):
    for _ in range(PAGINATION_TIMEOUT):
        html = await page.get_content()
        if html != previous_html:
            count = await page.evaluate('document.querySelectorAll("ul.resultats").length')
            if count > 0:
                return html
        await asyncio.sleep(1)

    return await page.get_content()


def parse_events_from_html(html, existing_events, all_results, existing_event_keys):
    soup = BeautifulSoup(html, "html.parser")
    result_lists = soup.find_all("ul", class_="resultats")
    page_events = []
    page_new = 0

    for result_list in result_lists:
        event_info = result_list.find_parent("div", class_="element")
        if not event_info:
            continue

        event_header = event_info.find("div", class_="element-header")
        event_name_raw = event_header.get_text(strip=True) if event_header else "Unknown Event"
        event_name = clean_event_name(event_name_raw)

        table_cell = event_info.find("div", class_="table1")
        if table_cell:
            date_location_text = table_cell.get_text(strip=True)
            date_location = " ".join(date_location_text.replace("\n", " ").split())
        else:
            date_location = "Unknown Date/Location"

        parsed_location = parse_date_location(date_location)

        colla_items = result_list.find_all("li")
        colles_data = []
        current_colla = None

        for item in colla_items:
            if "colla-name" in item.get("class", []):
                if current_colla:
                    colles_data.append(current_colla)
                current_colla = {
                    "colla_name": item.get_text(strip=True),
                    "castells": [],
                }
            elif current_colla:
                castell_data = parse_castell_result(item.get_text(strip=True))
                current_colla["castells"].append(castell_data)

        if current_colla:
            colles_data.append(current_colla)

        event_data = {
            "event_id": f"event_{len(existing_events) + len(all_results) + len(page_events) + 1}",
            "event_name": event_name,
            "date": parsed_location["date"],
            "time": parsed_location["time"],
            "place": parsed_location["place"],
            "city": parsed_location["city"],
            "raw_date_location": parsed_location["raw_text"],
            "colles": colles_data,
            "total_colles": len(colles_data),
            "total_castells": sum(len(colla["castells"]) for colla in colles_data),
            "scraped_at": datetime.now().isoformat(),
        }

        event_key_val = event_key(event_data)
        if event_key_val in existing_event_keys:
            print(
                f"  Skipping duplicate event: {event_name} on "
                f"{parsed_location['date']} in {parsed_location['city']}"
            )
            continue

        page_events.append(event_data)
        existing_event_keys.add(event_key_val)
        page_new += 1

    has_next = soup.find("a", {"rel": "next"}) is not None
    return page_events, page_new, has_next, soup


async def scrape_with_browser(date_start, date_end, existing_events, existing_event_keys):
    headless = os.environ.get("SCRAPER_HEADLESS", "true").lower() != "false"
    browser_args = ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
    chrome_path = resolve_browser_executable()

    start_kwargs = {
        "headless": headless,
        "sandbox": False,
        "browser_args": browser_args,
        "lang": "ca-ES",
    }
    if chrome_path:
        start_kwargs["browser_executable_path"] = chrome_path
        print(f"Using browser: {chrome_path} (headless={headless})")
    else:
        print(f"Using nodriver default browser (headless={headless})")

    cf_cookies, _ = fetch_flaresolverr_cookies(BASE_URL)
    if cf_cookies:
        print(f"Loaded {len(cf_cookies)} cookies from FlareSolverr")

    browser = await uc.start(**start_kwargs)
    all_results = []
    total_events = 0
    pages_scraped = 0

    try:
        page = await browser.get("about:blank")
        if cf_cookies:
            await apply_cookies(page, cf_cookies)

        page = await browser.get(BASE_URL)
        await wait_for_page_ready(page)
        await wait_for_turnstile(page)
        await submit_search(page, date_start, date_end)

        result_count = await wait_for_results(page)
        if result_count == 0:
            return all_results, total_events, pages_scraped

        while pages_scraped < MAX_PAGES:
            pages_scraped += 1
            print(f"Processing page {pages_scraped}...")

            html = await page.get_content()
            result_lists = BeautifulSoup(html, "html.parser").find_all("ul", class_="resultats")
            print(f"Found {len(result_lists)} events on page {pages_scraped}")

            page_events, page_new, has_next, _ = parse_events_from_html(
                html,
                existing_events,
                all_results,
                existing_event_keys,
            )
            all_results.extend(page_events)
            total_events += page_new

            if not has_next:
                print("No next page link found, stopping pagination")
                break

            previous_html = html
            clicked = await page.evaluate(
                '(() => { const link = document.querySelector(\'a[rel="next"]\'); '
                "if (!link) return false; link.click(); return true; })()"
            )
            if not clicked:
                print("Next page link not clickable, stopping pagination")
                break

            new_html = await wait_for_page_change(page, previous_html)
            if new_html == previous_html:
                print("Page content did not change after clicking next, stopping pagination")
                break

        return all_results, total_events, pages_scraped
    finally:
        browser.stop()


def save_results(all_results, existing_events, existing_metadata, date_start, date_end, page_num, total_events):
    new_events_stats = {
        "events_with_results": len([e for e in all_results if e["total_castells"] > 0]),
        "events_without_results": len([e for e in all_results if e["total_castells"] == 0]),
        "total_colles": sum(e["total_colles"] for e in all_results),
        "total_castells": sum(e["total_castells"] for e in all_results),
        "unique_cities": len(set(e["city"] for e in all_results if e["city"])),
        "unique_colles": len(
            set(colla["colla_name"] for e in all_results for colla in e["colles"])
        ),
    }

    all_events = existing_events + all_results
    search_parameters = {
        "date_start": date_start,
        "date_end": date_end,
        "diada": "",
        "colla_filter": "",
        "castell": "",
        "result": "",
        "city": "",
        "country": "",
        "colles_type": "all",
    }

    dataset = {
        "metadata": {
            "scraped_at": datetime.now().isoformat(),
            "total_events": len(all_events),
            "total_pages_scraped": page_num,
            "previous_scrape": existing_metadata.get("scraped_at"),
            "events_added_this_run": total_events,
            "search_parameters": search_parameters,
            "statistics": {
                "events_with_results": len([e for e in all_events if e["total_castells"] > 0]),
                "events_without_results": len([e for e in all_events if e["total_castells"] == 0]),
                "total_colles": sum(e["total_colles"] for e in all_events),
                "total_castells": sum(e["total_castells"] for e in all_events),
                "unique_cities": len(set(e["city"] for e in all_events if e["city"])),
                "unique_colles": len(
                    set(colla["colla_name"] for e in all_events for colla in e["colles"])
                ),
            },
            "new_events_statistics": new_events_stats,
        },
        "events": all_events,
    }

    if OUTPUT_FORMAT == "json":
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        print(f"Saved structured data to {OUTPUT_FILE}")

        summary = {
            "total_events": dataset["metadata"]["total_events"],
            "events_with_results": dataset["metadata"]["statistics"]["events_with_results"],
            "total_castells": dataset["metadata"]["statistics"]["total_castells"],
            "unique_colles": dataset["metadata"]["statistics"]["unique_colles"],
            "unique_cities": dataset["metadata"]["statistics"]["unique_cities"],
        }
        summary_path = os.path.join(SCRIPT_DIR, "..", "summary.json")
        with open(os.path.normpath(summary_path), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"Saved summary to {summary_path}")
    else:
        with open("results.txt", "w", encoding="utf-8") as f:
            for event_data in all_results:
                f.write(f"=== {event_data['event_name']} ===\n")
                f.write(f"Date/Location: {event_data['raw_date_location']}\n")
                for colla in event_data["colles"]:
                    f.write(f"\nColla: {colla['colla_name']}\n")
                    for castell in colla["castells"]:
                        f.write(f"  - {castell['raw_text']}\n")
                f.write("\n" + "=" * 50 + "\n\n")
        print("Saved results to results.txt")

    print(f"\nNew Events Statistics (from this scrape):")
    print(f"- Total new events: {total_events}")
    print(f"- Events with results: {new_events_stats['events_with_results']}")
    print(f"- Total castells: {new_events_stats['total_castells']}")
    print(f"- Unique colles: {new_events_stats['unique_colles']}")
    print(f"- Unique cities: {new_events_stats['unique_cities']}")

    print(f"\nTotal Dataset Statistics (all events):")
    print(f"- Total events: {dataset['metadata']['total_events']}")
    print(f"- Events with results: {dataset['metadata']['statistics']['events_with_results']}")
    print(f"- Total castells: {dataset['metadata']['statistics']['total_castells']}")
    print(f"- Unique colles: {dataset['metadata']['statistics']['unique_colles']}")
    print(f"- Unique cities: {dataset['metadata']['statistics']['unique_cities']}")


async def main():
    existing_events, existing_metadata = load_existing_events(OUTPUT_FILE)
    existing_event_keys = {event_key(event) for event in existing_events}
    print(f"Loaded {len(existing_events)} existing events. Will skip duplicates.")

    date_start = DATE_START if DATE_START else "01/01/2026"
    date_end = DATE_END if DATE_END else "17/02/2026"

    all_results, total_events, pages_scraped = await scrape_with_browser(
        date_start, date_end, existing_events, existing_event_keys
    )

    print(f"New events found in this scrape: {total_events}")
    print(f"Existing events: {len(existing_events)}")
    print(f"Total events after merge: {len(existing_events) + len(all_results)}")

    save_results(
        all_results,
        existing_events,
        existing_metadata,
        date_start,
        date_end,
        pages_scraped,
        total_events,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
