"""
One-time manual login helper for OAuth/SSO users (Google, LinkedIn, etc.).

Run this script once before using main.py if your JobRight account uses
single sign-on and can't be automated with email+password:

    python login.py

A headed browser will open. Log in manually (including any SSO flow).
The session will be saved to ./browser_data/ for all future headless runs.
"""

import asyncio
import sys

import config

WAIT_SECONDS = 120  # Give the user up to 2 minutes to log in


async def manual_login() -> None:
    from playwright.async_api import async_playwright

    print("[login] Opening headed browser for manual login...")
    print(f"[login] You have {WAIT_SECONDS} seconds to log in.")
    print("[login] After logging in, just wait — the browser will close automatically.")

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=config.BROWSER_DATA_DIR,
            headless=False,  # Always headed for manual login
        )

        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://jobright.ai/login", wait_until="domcontentloaded", timeout=30_000)

        print(f"[login] Browser is open. Waiting up to {WAIT_SECONDS}s for you to log in...")

        # Wait until the user is redirected away from the login page
        for i in range(WAIT_SECONDS):
            await asyncio.sleep(1)
            current_url = page.url
            if "login" not in current_url and "signin" not in current_url and "auth" not in current_url:
                print(f"[login] Detected successful login! Current URL: {current_url}")
                break
        else:
            print("[login] Timed out waiting for login. Session may not be saved correctly.")

        # Extra pause so any post-login redirects and token saves complete
        print("[login] Saving session — please wait 3 seconds...")
        await asyncio.sleep(3)
        await context.close()

    print(f"[login] Session saved to {config.BROWSER_DATA_DIR}/")
    print("[login] You can now run `python main.py` for headless operation.")


if __name__ == "__main__":
    try:
        asyncio.run(manual_login())
    except KeyboardInterrupt:
        print("\n[login] Cancelled.")
        sys.exit(0)
