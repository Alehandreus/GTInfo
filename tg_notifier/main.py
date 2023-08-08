from tg_notifier import TGNotifier
import asyncio
import os

# from dotenv import load_dotenv
# load_dotenv()


BIND_ADDRESS = (os.environ.get("BIND_HOST"), int(os.environ.get("BIND_PORT")))
WEBSITE_URL = f"http://{os.environ.get('WEBSITE_HOST')}:{os.environ.get('WEBSITE_PORT')}"

token = os.environ.get("TG_TOKEN")

a = TGNotifier(BIND_ADDRESS, WEBSITE_URL, token)
asyncio.run(a.start())
