import asyncio
import os
import random
import re
import sys
import threading
import time
import tkinter as tk
from queue import Queue
from tkinter import messagebox, scrolledtext, ttk

from playwright.async_api import async_playwright

# Configs
NUM_ATTEMPTS = 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    # Add more if you like
]

# Queue for communication between threads
log_queue = Queue()
result_queue = Queue()
# For stopping the process
cancel_event = threading.Event()


# Message handling functions
def log(msg):
    log_queue.put(msg)


def handle_results(result):
    result_queue.put(result)


class RedirectText:
    def __init__(self, queue):
        self.queue = queue

    def write(self, string):
        self.queue.put(string)

    def flush(self):
        pass


async def get_user_artworks(playwright, username):
    browser_type = playwright.chromium
    launch_options = {"headless": True}

    log(f"Fetching artworks for user: {username}...")

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
            log(f"Username '{username}' not found on ArtStation.")
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

        log(f"Found {len(artwork_links)} artworks for {username}")

        await browser.close()
        return artwork_links

    except Exception as e:
        log(f"Error fetching artworks: {e}")
        if "browser" in locals() and browser.is_connected():
            await browser.close()
        return []


async def run_view_process(
    username, option, specific_artwork=None, num_attempts=NUM_ATTEMPTS
):
    browser = None
    try:
        async with async_playwright() as p:
            # Fetch all artwork links for the user
            artwork_links = await get_user_artworks(p, username)

            if not artwork_links:
                handle_results(
                    {
                        "status": "error",
                        "message": "No artworks found or username doesn't exist.",
                    }
                )
                return

            artworks_to_view = []

            if option == 1:  # Latest artwork only
                artworks_to_view = [artwork_links[0]]
                log(f"Selected latest artwork: {artworks_to_view[0]}")

            elif option == 2:  # 5 latest artworks
                num_to_view = min(5, len(artwork_links))
                artworks_to_view = artwork_links[:num_to_view]
                log(f"Selected {num_to_view} latest artworks")

            elif option == 3:  # All artworks
                artworks_to_view = artwork_links
                log(f"Selected all {len(artworks_to_view)} artworks")

            elif option == 4:  # Specific artwork
                artwork_id = specific_artwork

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
                    log(f"Selected specific artwork: {matching_artwork}")
                else:
                    handle_results(
                        {
                            "status": "error",
                            "message": f"Artwork with ID '{artwork_id}' not found for this user.",
                        }
                    )
                    return

            # Process artworks in rounds (artwork 1, 2, 3, then repeat)
            total_successful = 0
            total_attempts = 0

            log(
                f"\n--- Starting {num_attempts} rounds of views for {len(artworks_to_view)} artworks ---"
            )

            # Create a single browser instance for reuse with new contexts
            browser_type = p.chromium
            browser = await browser_type.launch(headless=True)

            # Check if canceled before starting
            if cancel_event.is_set():
                log("Process was canceled before starting")
                await browser.close()
                handle_results({"status": "canceled"})
                return

            for attempt in range(num_attempts):
                log(f"\n--- Round {attempt+1}/{num_attempts} ---")

                # Check if canceled
                if cancel_event.is_set():
                    log("Process was canceled during execution")
                    break

                for i, artwork_url in enumerate(artworks_to_view):
                    # Check if canceled
                    if cancel_event.is_set():
                        log("Process was canceled during execution")
                        break

                    log(
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

                        scroll_time = random.uniform(1, 2)
                        await page.evaluate(
                            f"window.scrollBy(0, {random.randint(300, 600)});"
                        )
                        log(f"Page loaded. 'Viewing' for {scroll_time:.2f} seconds...")

                        # Check for cancellation during wait time
                        for _ in range(int(scroll_time * 2)):
                            if cancel_event.is_set():
                                break
                            await asyncio.sleep(0.5)

                        if not cancel_event.is_set():
                            log(f"Simulated view of {artwork_url}")
                            total_successful += 1

                        # Close the context but keep the browser open
                        await context.close()

                    except Exception as e:
                        log(f"Error viewing artwork: {e}")

                    total_attempts += 1

                    # Update progress
                    progress = (
                        total_attempts / (len(artworks_to_view) * num_attempts)
                    ) * 100
                    handle_results({"status": "progress", "value": progress})

                    # Check if canceled
                    if cancel_event.is_set():
                        break

                    # Add delay between artworks
                    if i < len(artworks_to_view) - 1 and not cancel_event.is_set():
                        delay = random.uniform(1, 2)
                        log(f"Waiting for {delay:.2f} seconds before next artwork...")

                        # Check for cancellation during delay
                        for _ in range(int(delay * 2)):
                            if cancel_event.is_set():
                                break
                            await asyncio.sleep(0.5)

                # Check if canceled
                if cancel_event.is_set():
                    break

                # Add longer delay between rounds
                if attempt < num_attempts - 1 and not cancel_event.is_set():
                    delay = random.uniform(3, 5)
                    log(
                        f"\nFinished round {attempt+1}. Waiting for {delay:.2f} seconds before next round..."
                    )

                    # Check for cancellation during delay
                    for _ in range(int(delay * 2)):
                        if cancel_event.is_set():
                            break
                        await asyncio.sleep(0.5)

            # Close the browser at the end
            if browser and browser.is_connected():
                await browser.close()

            if cancel_event.is_set():
                log("\n--- Process Canceled ---")
                handle_results({"status": "canceled"})
            else:
                log(f"\n--- Finished ---")
                log(
                    f"Attempted {total_attempts} views across {len(artworks_to_view)} artworks over {attempt+1} rounds."
                )
                log(f"Successfully completed views: {total_successful}.")
                log(
                    "--------------------------------------------------------------------"
                )
                log(
                    "IMPORTANT: Check your ArtStation posts to see if the view counts changed."
                )
                log(
                    "EXPECTATION: The view count will likely increase by only 1 (or very few)"
                )
                log("             per artwork, due to IP-based tracking by ArtStation.")
                log(
                    "--------------------------------------------------------------------"
                )

                handle_results(
                    {
                        "status": "complete",
                        "attempts": total_attempts,
                        "successful": total_successful,
                    }
                )

    except Exception as e:
        log(f"Error in view process: {e}")
        handle_results({"status": "error", "message": str(e)})
        if browser and browser.is_connected():
            await browser.close()


def start_view_process_thread(
    username, option, specific_artwork=None, num_attempts=NUM_ATTEMPTS
):
    # Clear the cancel event flag
    cancel_event.clear()

    def run():
        asyncio.run(run_view_process(username, option, specific_artwork, num_attempts))

    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    return thread


class ArtStationViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ArtStation View Booster")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)

        # Set app icon if we decide to add one later
        # self.root.iconbitmap("icon.ico")

        # Style
        self.style = ttk.Style()
        if sys.platform == "darwin":  # macOS
            self.style.theme_use("aqua")
        else:
            self.style.theme_use("clam")

        # Variables
        self.username_var = tk.StringVar()
        self.option_var = tk.IntVar(value=1)
        self.specific_artwork_var = tk.StringVar()
        self.num_attempts_var = tk.StringVar(value=str(NUM_ATTEMPTS))
        self.process_running = False
        self.view_thread = None

        # Create UI
        self.create_widgets()

        # Setup periodic log check
        self.root.after(100, self.check_log_queue)
        self.root.after(100, self.check_result_queue)

        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame, text="ArtStation View Booster", font=("Helvetica", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Warning
        warning_frame = ttk.Frame(main_frame)
        warning_frame.pack(fill=tk.X, pady=(0, 20))

        warning_label = ttk.Label(
            warning_frame,
            text="WARNING: Automating view counts is likely against ArtStation's ToS and can lead to account suspension.",
            foreground="red",
            wraplength=600,
        )
        warning_label.pack()

        # Input frame
        input_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        # Username
        username_frame = ttk.Frame(input_frame)
        username_frame.pack(fill=tk.X, pady=5)

        username_label = ttk.Label(
            username_frame, text="ArtStation Username:", width=20
        )
        username_label.pack(side=tk.LEFT)

        username_entry = ttk.Entry(username_frame, textvariable=self.username_var)
        username_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Options
        options_frame = ttk.LabelFrame(input_frame, text="View Options", padding="10")
        options_frame.pack(fill=tk.X, pady=5)

        option1 = ttk.Radiobutton(
            options_frame,
            text="Latest artwork only",
            variable=self.option_var,
            value=1,
            command=self.toggle_specific_artwork,
        )
        option1.grid(row=0, column=0, sticky=tk.W, pady=2)

        option2 = ttk.Radiobutton(
            options_frame,
            text="5 latest artworks",
            variable=self.option_var,
            value=2,
            command=self.toggle_specific_artwork,
        )
        option2.grid(row=1, column=0, sticky=tk.W, pady=2)

        option3 = ttk.Radiobutton(
            options_frame,
            text="All artworks",
            variable=self.option_var,
            value=3,
            command=self.toggle_specific_artwork,
        )
        option3.grid(row=2, column=0, sticky=tk.W, pady=2)

        option4 = ttk.Radiobutton(
            options_frame,
            text="Specific artwork",
            variable=self.option_var,
            value=4,
            command=self.toggle_specific_artwork,
        )
        option4.grid(row=3, column=0, sticky=tk.W, pady=2)

        # Specific artwork frame
        self.specific_frame = ttk.Frame(options_frame)
        self.specific_frame.grid(row=4, column=0, sticky=tk.W, pady=2, padx=(20, 0))

        specific_label = ttk.Label(self.specific_frame, text="Artwork ID or URL:")
        specific_label.pack(side=tk.LEFT)

        specific_entry = ttk.Entry(
            self.specific_frame, textvariable=self.specific_artwork_var, width=30
        )
        specific_entry.pack(side=tk.LEFT, padx=(5, 0))

        self.specific_frame.grid_remove()  # Hide initially

        # Number of attempts
        attempts_frame = ttk.Frame(input_frame)
        attempts_frame.pack(fill=tk.X, pady=5)

        attempts_label = ttk.Label(attempts_frame, text="Number of rounds:", width=20)
        attempts_label.pack(side=tk.LEFT)

        attempts_entry = ttk.Entry(
            attempts_frame, textvariable=self.num_attempts_var, width=10
        )
        attempts_entry.pack(side=tk.LEFT, padx=(5, 0))

        # Start button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        self.start_button = ttk.Button(
            button_frame, text="Start View Process", command=self.start_process
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(
            button_frame, text="Stop", command=self.stop_process, state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Progress
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=10)

        progress_label = ttk.Label(progress_frame, text="Progress:")
        progress_label.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(
            progress_frame, orient=tk.HORIZONTAL, length=100, mode="determinate"
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        # Copyright
        copyright_label = ttk.Label(
            main_frame,
            text="© 2023 ArtStation View Booster. For educational purposes only.",
        )
        copyright_label.pack(pady=(10, 0))

    def toggle_specific_artwork(self):
        if self.option_var.get() == 4:
            self.specific_frame.grid()
        else:
            self.specific_frame.grid_remove()

    def start_process(self):
        # Validate inputs
        username = self.username_var.get().strip()
        if not username:
            messagebox.showerror("Error", "Please enter an ArtStation username")
            return

        option = self.option_var.get()
        specific_artwork = (
            self.specific_artwork_var.get().strip() if option == 4 else None
        )

        if option == 4 and not specific_artwork:
            messagebox.showerror("Error", "Please enter an artwork ID or URL")
            return

        try:
            num_attempts = int(self.num_attempts_var.get())
            if num_attempts <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Number of rounds must be a positive integer")
            return

        # Clear log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        # Update UI
        self.process_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress_bar["value"] = 0

        # Launch the process
        self.add_to_log("Starting view process...\n")
        self.view_thread = start_view_process_thread(
            username, option, specific_artwork, num_attempts
        )

    def stop_process(self):
        if messagebox.askyesno(
            "Confirm Stop", "Are you sure you want to stop the current process?"
        ):
            self.add_to_log("\nStopping process... (This may take a moment)\n")
            # Set the cancellation flag
            cancel_event.set()
            self.process_running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def on_close(self):
        # Ensure process is stopped when closing the window
        if self.process_running:
            cancel_event.set()
            self.add_to_log("\nStopping process due to application close...\n")
            # Give a moment for thread to acknowledge cancellation
            time.sleep(0.5)
        self.root.destroy()

    def add_to_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def check_log_queue(self):
        while not log_queue.empty():
            message = log_queue.get()
            self.add_to_log(message + "\n")

        self.root.after(100, self.check_log_queue)

    def check_result_queue(self):
        while not result_queue.empty():
            result = result_queue.get()

            if result["status"] == "progress":
                self.progress_bar["value"] = result["value"]

            elif result["status"] == "complete":
                self.process_running = False
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.progress_bar["value"] = 100
                messagebox.showinfo(
                    "Complete",
                    f"View process completed!\n\n"
                    f"Total attempts: {result['attempts']}\n"
                    f"Successful views: {result['successful']}",
                )

            elif result["status"] == "canceled":
                self.process_running = False
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.add_to_log("Process successfully stopped.")

            elif result["status"] == "error":
                self.process_running = False
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                messagebox.showerror("Error", result["message"])

        self.root.after(100, self.check_result_queue)


def main():
    # Redirect stdout to our queue
    sys.stdout = RedirectText(log_queue)

    # Create and run the app
    root = tk.Tk()
    app = ArtStationViewerApp(root)
    root.mainloop()

    # Restore stdout when done
    sys.stdout = sys.__stdout__


if __name__ == "__main__":
    main()
