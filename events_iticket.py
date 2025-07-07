import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import logging
import re

# Configure logging (ensure this is at the top of your file)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
ITICKET_BASE_URL = "https://iticket.md"
CATEGORY_URLS = {
    "teatru": f"{ITICKET_BASE_URL}/events/teatru",
    "concerte": f"{ITICKET_BASE_URL}/events/concerte",
    "petreceri": f"{ITICKET_BASE_URL}/events/petreceri",
    "copii": f"{ITICKET_BASE_URL}/events/copii",
    "stand-up": f"{ITICKET_BASE_URL}/events/stand-up",
    "alte-evenimente": f"{ITICKET_BASE_URL}/events/alte-evenimente"
}

# Romanian to English month mapping for comparison
MONTH_MAPPING = {
    "ian": "jan", "feb": "feb", "mar": "mar", "apr": "apr",
    "mai": "may", "iun": "jun", "iul": "jul", "aug": "aug",
    "sep": "sep", "oct": "oct", "noi": "nov", "dec": "dec"
}

# Timezone for Moldova (EET/EEST)
TZ = pytz.timezone('Europe/Chisinau')

# Training blacklist to avoid posting events that are not relevant or duplicates
TRAINING_BLACKLIST = [
    "în curând", # "Coming soon"
    "test",
    # Add other irrelevant event titles or keywords here
]

async def fetch_html(url: str) -> str | None:
    """Fetches HTML content from a given URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as response:
                response.raise_for_status()  # Raise an exception for bad status codes
                return await response.text()
    except aiohttp.ClientError as e:
        logging.error(f"Network error fetching {url}: {e}")
        return None
    except asyncio.TimeoutError:
        logging.error(f"Timeout fetching {url}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching {url}: {e}")
        return None

def extract_event_data(card: BeautifulSoup) -> dict | None:
    """Extracts event details from a single event card."""
    try:
        # Extract title
        title_element = card.select_one(".e-c-name")
        title = title_element.get_text(strip=True) if title_element else "N/A"

        # Check against training blacklist
        if any(keyword in title.lower() for keyword in TRAINING_BLACKLIST):
            logging.info(f"Skipping blacklisted event: {title}")
            return None

        # Extract date (day number)
        date_element = card.select_one(".e-c-time span")
        date = date_element.get_text(strip=True) if date_element else "N/A"

        # Extract month
        month_element = card.select_one(".e-c-month")
        month = month_element.get_text(strip=True) if month_element else "N/A"

        # Extract location/venue
        location_element = card.select_one(".e-c-location-title")
        location = location_element.get_text(strip=True) if location_element else "N/A"

        # Extract image URL
        img_element = card.select_one(".e-c-image img")
        image_url = img_element['src'] if img_element and 'src' in img_element.attrs else "N/A"
        # Prepend base URL if image_url is relative
        if image_url and image_url != "N/A" and not image_url.startswith('http'):
            image_url = ITICKET_BASE_URL + image_url

        # Extract event URL
        event_url_element = card.select_one("a")
        event_url = event_url_element['href'] if event_url_element and 'href' in event_url_element.attrs else "N/A"
        # Prepend base URL if event_url is relative
        if event_url and event_url != "N/A" and not event_url.startswith('http'):
            event_url = ITICKET_BASE_URL + event_url

        # Extract price (meta itemprop="price")
        price_element = card.select_one('meta[itemprop="price"]')
        price = price_element['content'] if price_element and 'content' in price_element.attrs else "N/A"
        
        # Extract priceCurrency (meta itemprop="priceCurrency")
        price_currency_element = card.select_one('meta[itemprop="priceCurrency"]')
        price_currency = price_currency_element['content'] if price_currency_element and 'content' in price_currency_element.attrs else "MDL" # Default to MDL

        # Combine price and currency
        full_price = f"{price} {price_currency}" if price != "N/A" else "N/A"

        return {
            "title": title,
            "date": date,
            "month": month,
            "location": location,
            "image_url": image_url,
            "event_url": event_url,
            "price": full_price,
        }
    except AttributeError:
        logging.warning(f"Skipping event card due to missing expected elements. Card HTML: {card}")
        return None
    except Exception as e:
        logging.error(f"Error extracting event data from card: {e}. Card HTML: {card}")
        return None

def match_today(event: dict) -> bool:
    """Checks if the event's date and month match today's date and month."""
    now = datetime.now(TZ)
    expected_day = str(now.day)
    expected_month = now.strftime('%b').lower().replace('.', '') # e.g., 'jul'

    actual_day_raw = event["date"]
    actual_month_ro = event["month"].lower().replace('.', '') # Remove dot from month e.g., 'iul'

    translated_month = MONTH_MAPPING.get(actual_month_ro, actual_month_ro)

    # Use regex to extract the day number, handling leading zeros or other characters
    day_match = re.match(r"(\d+)", actual_day_raw)
    actual_day = day_match.group(1) if day_match else None

    logging.info(f"Checking event: Title='{event['title']}', Scraped Date='{actual_day_raw}', Scraped Month='{actual_month_ro}'")
    logging.info(f"  -> Parsed Day: '{actual_day}', Translated Month: '{translated_month}'")
    logging.info(f"  -> Expected Day: '{expected_day}', Expected Month: '{expected_month}'")

    day_matches = False
    if actual_day: # Ensure a day was successfully extracted
        # Direct match (e.g., '5' == '5')
        if actual_day == expected_day:
            day_matches = True
        # Handle cases where scraped day might be '05' for '5'
        elif actual_day.lstrip('0') == expected_day:
            day_matches = True
        # Handle cases where scraped day might be '5–' or similar, by checking start
        elif actual_day.startswith(expected_day):
            day_matches = True

    month_matches = (translated_month == expected_month)

    result = day_matches and month_matches
    logging.info(f"  -> Day Matches: {day_matches}, Month Matches: {month_matches}, Overall Match: {result}")
    return result

async def events_iticket_job() -> list[dict]: # Renamed to events_iticket_job
    """
    Collects events for today from all specified categories on iticket.md.
    This function is intended to be called by APScheduler.
    """
    logging.info("Starting iTicket.md scraping job...")
    all_events = []
    today_events = []

    for category, url in CATEGORY_URLS.items():
        logging.info(f"Scraping events from category: {category} ({url})")
        html_content = await fetch_html(url)
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            event_cards = soup.find_all('div', class_='event-card')
            logging.info(f"Found {len(event_cards)} event cards in category: {category}")

            for card in event_cards:
                event = extract_event_data(card)
                if event:
                    all_events.append(event)
        else:
            logging.warning(f"Could not retrieve HTML for category: {category}")

    logging.info(f"Total raw events collected: {len(all_events)}")

    for event in all_events:
        if match_today(event):
            today_events.append(event)
        else:
            logging.info(f"Skipping event as it does not match today: {event['title']}")

    logging.info(f"Total events matching today: {len(today_events)}")
    
    # You will likely want to add your Telegram posting logic here,
    # or ensure that your run.py handles the 'today_events' returned by this function.
    if today_events:
        logging.info("Events for today:")
        for event in today_events:
            logging.info(f"  - Title: {event['title']}")
            logging.info(f"    Date: {event['date']} {event['month']}")
            logging.info(f"    Location: {event['location']}")
            logging.info(f"    Price: {event['price']}")
            logging.info(f"    URL: {event['event_url']}")
            logging.info(f"    Image: {event['image_url']}")
            logging.info("-" * 20)
    else:
        logging.info("No events found for today.")
    
    logging.info("iTicket.md scraping job finished.")
    return today_events # Return the list of events for today

# Removed the main() and if __name__ == "__main__": block
# as this file is now intended to be imported by run.py