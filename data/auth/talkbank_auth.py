from pathlib import Path

from playwright.sync_api import sync_playwright


SCRIPT_DIR = Path(__file__).resolve().parent
AUTH_FILE = SCRIPT_DIR / "talkbank_auth.json"

LOGIN_URL = "https://sla.talkbank.org/TBB/phon/Eng-NA/"


def authenticate():

    print("Opening TalkBank login page...")
    print("Sign in using the browser window that opens.")
    print("After signing in, return to this terminal and press ENTER.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            input("\nOnce you are signed into TalkBank, press ENTER here... ")

            context.storage_state(path=str(AUTH_FILE))
            print(f"Authentication state saved to: {AUTH_FILE}")
        finally:
            context.close()
            browser.close()

def deauthenticate():
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()
        print("Destroyed authentication JSON.")


if __name__ == "__main__":
    authenticate()
