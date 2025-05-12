import asyncio
import random
import re
import time

from playwright.async_api import async_playwright

# Configs
NUM_ATTEMPTS = 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    # Add more if you like
]


async def view_post_fresh_context(playwright, artwork_url):
    browser_type = playwright.chromium
    launch_options = {"headless": True}  # Keep headless true for automation

    print(
        f"Attempting view with a new browser context (fresh cookies, no proxy) for {artwork_url}..."
    )

    try:
        browser = await browser_type.launch(**launch_options)

        # Create a new isolated browser context for fresh cookies/storage
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            java_script_enabled=True,
        )
        page = await context.new_page()

        await page.goto(artwork_url, timeout=60000, wait_until="networkidle")

        scroll_time = random.uniform(2, 5)
        await page.evaluate(f"window.scrollBy(0, {random.randint(300, 600)});")
        print(f"Page loaded. 'Viewing' for {scroll_time:.2f} seconds...")
        await asyncio.sleep(scroll_time)

        print(f"Simulated view of {artwork_url} with fresh context.")

        await context.close()
        await browser.close()
        return True

    except Exception as e:
        print(f"Error during fresh context view: {e}")
        if "browser" in locals() and browser.is_connected():
            await browser.close()
        return False


async def get_user_artworks(playwright, username):
    browser_type = playwright.chromium
    launch_options = {"headless": True}

    print(f"Fetching artworks for user: {username}...")

    try:
        browser = await browser_type.launch(**launch_options)
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            java_script_enabled=True,
        )
        page = await context.new_page()

        user_url = f"https://www.artstation.com/{username}"
        await page.goto(user_url, timeout=60000, wait_until="networkidle")

        # Check if username exists
        if "/not-found" in page.url:
            print(f"Username '{username}' not found on ArtStation.")
            await browser.close()
            return []

        # Get all artwork links
        artwork_links = await page.evaluate(
            """
            () => {
                const links = document.querySelectorAll('a.gallery-grid-link');
                return Array.from(links).map(link => link.href);
            }
        """
        )

        print(f"Found {len(artwork_links)} artworks for {username}")

        await browser.close()
        return artwork_links

    except Exception as e:
        print(f"Error fetching artworks: {e}")
        if "browser" in locals() and browser.is_connected():
            await browser.close()
        return []


async def main():
    # Get username from user
    username = input("Enter ArtStation username: ").strip()

    async with async_playwright() as p:
        # Fetch all artwork links for the user
        artwork_links = await get_user_artworks(p, username)

        if not artwork_links:
            print("No artworks found or username doesn't exist. Exiting.")
            return

        # Display options to user
        print("\nChoose an option:")
        print("1. Increase views for the latest artwork only")
        print("2. Increase views for the 5 latest artworks")
        print("3. Increase views for all artworks")
        print("4. Increase views for a specific artwork")

        option = input("\nEnter option (1-4): ").strip()

        artworks_to_view = []

        if option == "1":
            artworks_to_view = [artwork_links[0]]
            print(f"Selected latest artwork: {artworks_to_view[0]}")

        elif option == "2":
            num_to_view = min(5, len(artwork_links))
            artworks_to_view = artwork_links[:num_to_view]
            print(f"Selected {num_to_view} latest artworks")

        elif option == "3":
            artworks_to_view = artwork_links
            print(f"Selected all {len(artworks_to_view)} artworks")

        elif option == "4":
            artwork_id = input("Enter artwork ID or full URL: ").strip()

            # Check if it's a full URL or just an ID
            if "artstation.com/artwork/" in artwork_id:
                # Extract the ID from the URL
                id_match = re.search(r"artstation\.com/artwork/([^/]+)", artwork_id)
                if id_match:
                    artwork_id = id_match.group(1)

            # Find matching artwork
            matching_artwork = None
            for link in artwork_links:
                if f"/artwork/{artwork_id}" in link:
                    matching_artwork = link
                    break

            if matching_artwork:
                artworks_to_view = [matching_artwork]
                print(f"Selected specific artwork: {matching_artwork}")
            else:
                print(f"Artwork with ID '{artwork_id}' not found for this user.")
                return
        else:
            print("Invalid option. Exiting.")
            return

        # Get number of view attempts per artwork
        try:
            num_attempts = int(
                input(
                    f"\nEnter number of view attempts per artwork (default: {NUM_ATTEMPTS}): "
                )
                or NUM_ATTEMPTS
            )
        except ValueError:
            num_attempts = NUM_ATTEMPTS
            print(f"Invalid input. Using default: {NUM_ATTEMPTS}")

        # Process artworks in rounds (artwork 1, 2, 3, then repeat)
        total_successful = 0
        total_attempts = 0

        print(
            f"\n--- Starting {num_attempts} rounds of views for {len(artworks_to_view)} artworks ---"
        )

        # Create a single browser instance for reuse with new contexts
        browser_type = p.chromium
        browser = await browser_type.launch(headless=True)

        for attempt in range(num_attempts):
            print(f"\n--- Round {attempt+1}/{num_attempts} ---")

            for i, artwork_url in enumerate(artworks_to_view):
                print(
                    f"\nProcessing artwork {i+1}/{len(artworks_to_view)}: {artwork_url}"
                )

                try:
                    # Create a new context for each artwork (maintains cookies separation)
                    context = await browser.new_context(
                        user_agent=random.choice(USER_AGENTS),
                        java_script_enabled=True,
                    )
                    page = await context.new_page()

                    await page.goto(
                        artwork_url, timeout=60000, wait_until="networkidle"
                    )

                    scroll_time = random.uniform(2, 5)
                    await page.evaluate(
                        f"window.scrollBy(0, {random.randint(300, 600)});"
                    )
                    print(f"Page loaded. 'Viewing' for {scroll_time:.2f} seconds...")
                    await asyncio.sleep(scroll_time)

                    print(f"Simulated view of {artwork_url}")
                    total_successful += 1

                    # Close the context but keep the browser open
                    await context.close()

                except Exception as e:
                    print(f"Error viewing artwork: {e}")

                total_attempts += 1

                # Add delay between artworks
                if i < len(artworks_to_view) - 1:
                    delay = random.uniform(3, 8)
                    print(f"Waiting for {delay:.2f} seconds before next artwork...")
                    await asyncio.sleep(delay)

            # Add longer delay between rounds
            if attempt < num_attempts - 1:
                delay = random.uniform(10, 20)
                print(
                    f"\nFinished round {attempt+1}. Waiting for {delay:.2f} seconds before next round..."
                )
                await asyncio.sleep(delay)

        # Close the browser at the end
        await browser.close()

        print(f"\n--- Finished ---")
        print(
            f"Attempted {total_attempts} views across {len(artworks_to_view)} artworks over {num_attempts} rounds."
        )
        print(f"Successfully completed views: {total_successful}.")
        print("--------------------------------------------------------------------")
        print(
            "IMPORTANT: Check your ArtStation posts to see if the view counts changed."
        )
        print(
            "EXPECTATION: The view count will likely increase by only 1 (or very few)"
        )
        print("             per artwork, due to IP-based tracking by ArtStation.")
        print("--------------------------------------------------------------------")


if __name__ == "__main__":
    print("*******************************************************************")
    print("WARNING: Automating view counts is likely against ArtStation's ToS")
    print("and can lead to account suspension. Use at your own risk.")
    print("This script is for educational purposes to understand automation.")
    print("*******************************************************************\n")
    asyncio.run(main())
