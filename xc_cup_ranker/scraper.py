import json
import sys
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from xc_cup_ranker.config import CURRENT_YEAR, TIMEOUT
from xc_cup_ranker.participants import get_participants
from xc_cup_ranker.utils import logger

ROUTE_TYPES = {
    "FREE_FLIGHT": "Free Flight",
    "FREE_TRIANGLE": "Free Triangle",
    "FAI_TRIANGLE": "FAI Triangle",
    "FLAT_TRIANGLE": "Flat Triangle",
}


def get_flights(
    year: int, event_id: int, date: str, take_off_site: str
) -> dict[str, dict]:
    """
    Fetches flights from XContest's internal API and returns a dictionary
    of relevant flights (matching take-off site and participants).
    :param year: Year of the event
    :param event_id: ID of the event
    :param date: Date of the event
    :param take_off_site: Take off site of the event
    :return: Dictionary of relevant flights
    """
    participants = get_participants(year, event_id)

    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)

    try:
        base_url = (
            f"https://www.xcontest.org/"
            f"{f'{year}/' if year != CURRENT_YEAR else ''}"
            f"switzerland/en/flights/daily-score-pg/"
            f"#filter[date]={date}@filter[country]=CH@filter[detail_glider_catg]=FAI3"
        )
        driver.get(base_url)

        WebDriverWait(driver, TIMEOUT).until(
            lambda d: d.find_element(By.CLASS_NAME, "XClist"),
        )

        api_url = driver.execute_script(
            """
            var entries = performance.getEntriesByType("resource");
            for (var i = 0; i < entries.length; i++) {
                if (entries[i].name.includes("/api/data/?flights/")) {
                    return entries[i].name;
                }
            }
            return null;
            """
        )

        if not api_url:
            logger.error("Could not discover XContest API URL")
            sys.exit(1)

        big_api_url = api_url.replace("list[num]=100", "list[num]=10000")

        data = driver.execute_async_script(
            """
            var callback = arguments[arguments.length - 1];
            fetch(arguments[0])
                .then(r => r.text())
                .then(text => callback(JSON.parse(text)))
                .catch(err => callback({error: err.toString()}));
            """,
            big_api_url,
        )

        if "error" in data and "items" not in data:
            logger.error(f"XContest API error: {data.get('error', data)}")
            sys.exit(1)

        items = data.get("items", [])
        total = data.get("list", {}).get("numberItems", len(items))
        logger.info(f"Total flights found: {total}")

        ranked_flights: dict[str, dict] = {}
        rank = 1

        for item in items:
            launch_site = item["takeoff"]["name"]
            pilot_name = item["pilot"]["name"]

            if (
                launch_site == take_off_site
                and pilot_name not in ranked_flights
                and pilot_name in participants
            ):
                ranked_flights[pilot_name] = _extract_flight(item, rank)
                rank += 1

        logger.info(f"Ranked flights: {len(ranked_flights)}")
        return ranked_flights

    finally:
        driver.quit()


def _extract_flight(item: dict, rank: int) -> dict:
    utc_time = datetime.fromisoformat(
        item["pointStart"]["time"].replace("Z", "+00:00")
    )
    offset = timedelta(seconds=item.get("utcOffsetStart", 0))
    local_time = utc_time + offset

    route = item["league"]["route"]

    return {
        "rank": rank,
        "take_off_time": local_time.strftime("%H:%M"),
        "route_type": ROUTE_TYPES.get(route["type"], route["type"]),
        "distance": f'{route["distance"]}',
        "points": f'{route["points"]}',
        "avg_speed": f'{route["avgSpeed"]:.1f}',
        "glider": item["glider"]["name"],
    }
