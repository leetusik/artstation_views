import asyncio
import random
import time

from playwright.async_api import async_playwright

# Configs
ARTSTATION_POST_URL = "https://www.artstation.com/artwork/x3xZ1m"
NUM_ATTEMPTS = 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    # Add more if you like
]


async def view_post_fresh_context(playwright):
    browser_type = playwright.chromium
    launch_options = {"headless": True}  # Keep headless true for automation

    print("Attempting view with a new browser context (fresh cookies, no proxy)...")

    try:
        browser = await browser_type.launch(**launch_options)

        # Create a new isolated browser context for fresh cookies/storage
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            java_script_enabled=True,
        )
        page = await context.new_page()

        await page.goto(ARTSTATION_POST_URL, timeout=60000, wait_until="networkidle")

        scroll_time = random.uniform(2, 5)
        await page.evaluate(f"window.scrollBy(0, {random.randint(300, 600)});")
        print(f"Page loaded. 'Viewing' for {scroll_time:.2f} seconds...")
        await asyncio.sleep(scroll_time)

        print(f"Simulated view of {ARTSTATION_POST_URL} with fresh context.")

        await context.close()
        await browser.close()
        return True

    except Exception as e:
        print(f"Error during fresh context view: {e}")
        if "browser" in locals() and browser.is_connected():
            await browser.close()
        return False


async def main():
    async with async_playwright() as p:
        successful_simulations = 0
        initial_view_count = (
            -1
        )  # You'd need to fetch this manually or via another script
        print(
            f"Before starting, please manually check the current view count for {ARTSTATION_POST_URL}"
        )
        input("Press Enter to continue after checking the view count...")

        for i in range(NUM_ATTEMPTS):
            print(f"\n--- Attempt {i+1}/{NUM_ATTEMPTS} ---")

            if await view_post_fresh_context(p):
                successful_simulations += 1

            # A delay is still good practice, even if not strictly for IP rotation here
            # It gives the server time and is less aggressive.
            # Artstation might also have internal delays in updating view counts.
            delay = random.uniform(5, 15)  # Shorter delay as we are not rotating IPs
            if i < NUM_ATTEMPTS - 1:
                print(f"Waiting for {delay:.2f} seconds before next attempt...")
                await asyncio.sleep(delay)

        print(f"\n--- Finished ---")
        print(f"Attempted {NUM_ATTEMPTS} simulations with fresh browser contexts.")
        print(f"Successfully completed simulations: {successful_simulations}.")
        print("--------------------------------------------------------------------")
        print(
            "IMPORTANT: Check your ArtStation post NOW to see if the view count changed."
        )
        print(
            "EXPECTATION: The view count will likely increase by only 1 (or very few),"
        )
        print(
            "             regardless of NUM_ATTEMPTS, due to IP-based tracking by ArtStation."
        )
        print(
            "             The script simulates new cookies/sessions perfectly, but not new users (IPs)."
        )
        print("--------------------------------------------------------------------")


if __name__ == "__main__":
    print("*******************************************************************")
    print("WARNING: Automating view counts is likely against ArtStation's ToS")
    print("and can lead to account suspension. Use at your own risk.")
    print("This script is for educational purposes to understand automation.")
    print("*******************************************************************\n")
    asyncio.run(main())
