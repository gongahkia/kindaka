# ----- REQUIRED IMPORTS -----

import time
import json
import asyncio
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright, Page, ElementHandle
from typing import Dict, List, Any, Optional
import base64
from pathlib import Path

# ----- HELPER FUNCTIONS -----


def pretty_print_json(json_object):
    """
    pretty prints the json to
    the cli for easy viewing
    """
    print(json.dumps(json_object, indent=4))


async def scrape_all_strava(athlete_id_array: List[str]) -> Dict[str, Any]:
    """
    wrapper function for easier user interfacing for multiple athletes
    """
    start_time = time.time()
    for athlete_id in athlete_id_array:
        url = f"https://www.strava.com/athletes/{athlete_id}"
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 1024}
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="networkidle")
                output_dir = Path("activity_screenshots")
                output_dir.mkdir(exist_ok=True)
                profile_data = await extract_profile_data(page)
                stats_data = await extract_stats_data(page)
                activities_count, activity_screenshots = await extract_activities(
                    page, output_dir
                )
                duration = time.time() - start_time
                scraped_data = {
                    "metadata": {
                        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "target_url": url,
                        "duration": f"{duration:.2f} seconds",
                        "num_users": len(athlete_id_array),
                    },
                    "user_data": [
                        {
                            "profile": profile_data,
                            "stats": stats_data,
                            "activities": activities_count,
                        }
                    ],
                }
                return scraped_data
            finally:
                await browser.close()


async def scrape_strava(athlete_id: str) -> Dict[str, Any]:
    """
    wrapper function for easier user interfacing for a single athlete
    """
    start_time = time.time()
    url = f"https://www.strava.com/athletes/{athlete_id}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 1024})
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle")
            output_dir = Path("activity_screenshots")
            output_dir.mkdir(exist_ok=True)
            profile_data = await extract_profile_data(page)
            stats_data = await extract_stats_data(page)
            activities_count, activity_screenshots = await extract_activities(
                page, output_dir
            )
            duration = time.time() - start_time
            scraped_data = {
                "metadata": {
                    "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "target_url": url,
                    "duration": f"{duration:.2f} seconds",
                    "num_users": 1,
                },
                "user_data": [
                    {
                        "profile": profile_data,
                        "stats": stats_data,
                        "activities": activities_count,
                    }
                ],
            }
            return scraped_data
        finally:
            await browser.close()


async def extract_profile_data(page: Page) -> Dict[str, Any]:
    """
    extract an athlete's strava profile page user data
    """
    athlete_name = (
        await page.locator(
            "div.profile-heading.profile.section div.spans5 h1.text-title1.athlete-name"
        ).inner_text()
        or ""
    )
    athlete_join_date = (
        await page.locator(
            "div.profile-heading.profile.section div.spans5 h1.text-title1.athlete-name"
        ).get_attribute("title")
        or ""
    )
    athlete_title = (
        await page.locator(
            "div.profile-heading.profile.section div.spans5 div.athlete-title"
        ).inner_text()
        or ""
    )
    athlete_profile_image = (
        await page.locator(
            "div.profile-heading.profile.section div.avatar-content img.avatar-img"
        ).get_attribute("src")
        or ""
    )
    athlete_location = (
        await page.locator(
            "div.profile-heading.profile.section div.spans5 div.location"
        ).inner_text()
        or ""
    )
    athlete_bio = (
        await page.locator(
            "div.profile-heading.profile.section div.spans5 div#athlete-description"
        ).inner_text()
        or ""
    )
    following_elements = await page.locator(
        "div.section.connections ul.inline-stats li"
    ).all()
    athlete_following = ""
    for element in following_elements:
        label = await element.locator("span.label.static-label").inner_text()
        if "Following" in label:
            athlete_following = await element.locator("a").inner_text()
            break
    followers_elements = await page.locator(
        "div.section.connections ul.inline-stats li"
    ).all()
    athlete_followers = ""
    for element in followers_elements:
        label = await element.locator("span.label.static-label").inner_text()
        if "Followers" in label:
            athlete_followers = await element.locator("a").inner_text()
            break
    athlete_clubs = []
    club_elements = await page.locator("ul.grid.clubs li").all()
    for club in club_elements:
        club_title = await club.locator("div").get_attribute("original-title") or ""
        club_url = await club.locator("a").get_attribute("href") or ""
        club_img = await club.locator("img").get_attribute("src") or ""
        athlete_clubs.append({"title": club_title, "url": club_url, "image": club_img})
    athlete_gear = []
    gear_rows = (
        await page.locator("div.section.stats.gear.shoes.hidden table tbody tr").all()
        or []
    )
    if gear_rows:
        for row in gear_rows:
            gear_text = await row.inner_text()
            athlete_gear.append(gear_text)
    data = {
        "athlete_name": athlete_name,
        "athlete_profile_image": athlete_profile_image,
        "athlete_bio": athlete_bio,
        "athlete_title": athlete_title,
        "athlete_join_date": athlete_join_date,
        "athlete_location": athlete_location,
        "athlete_following": athlete_following,
        "athlete_followers": athlete_followers,
        "athlete_clubs": athlete_clubs,
        "athlete_gear": athlete_gear,
    }
    pretty_print_json(data)
    return data


async def extract_stats_data(page: Page) -> Dict[str, Any]:
    """
    extract an athlete's strava profile page stats data
    """
    total_activities = await page.locator(
        "section.activity-summary-v2 div.activity-count div.count-total"
    ).inner_text()
    trophies = []
    trophy_elements = await page.locator(
        "div#trophy-case-summary ul.list-block-grid.list-trophies li"
    ).all()
    for trophy in trophy_elements:
        trophy_title = await trophy.get_attribute("title") or ""
        trophy_url = await trophy.locator("a").get_attribute("href") or ""
        trophies.append({"title": trophy_title, "url": trophy_url})
    achievements = []
    achievement_elements = await page.locator(
        "div.section.athlete-achievements ul li"
    ).all()
    for achievement in achievement_elements:
        achievement_text = await achievement.inner_text()
        achievement_date = (
            await achievement.locator("time").get_attribute("datetime") or ""
        )
        achievements.append({"text": achievement_text, "date": achievement_date})
    return {
        "total_activities_last_month": total_activities,
        "trophies": trophies,
        "achievements": achievements,
    }


async def extract_activities(page: Page, output_dir: Path) -> tuple[int, List[str]]:
    """
    screenshot an athlete's strava profile page activity data
    """
    activity_elements = await page.locator("main#main div.feature-feed > div").all()
    activity_screenshots = []
    for i, activity in enumerate(activity_elements):
        screenshot_path = output_dir / f"activity_{i+1}.png"
        await activity.screenshot(path=str(screenshot_path))
        activity_screenshots.append(str(screenshot_path))
    return len(activity_screenshots), activity_screenshots


async def main():
    """
    main scraper function for debugging
    """
    athlete_id = "26683816"
    log_filepath = "log.json"
    result = await scrape_strava(athlete_id)
    with open(log_filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Scraping completed. Data saved to {log_filepath}")


# ----- SAMPLE EXECUTION CODE -----

if __name__ == "__main__":
    asyncio.run(main())
