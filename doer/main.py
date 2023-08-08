from doer import Doer
import os

# from dotenv import load_dotenv
# load_dotenv()

SERVER_ADDRESS = (os.environ.get("DB_SERVER_HOST"), int(os.environ.get("DB_SERVER_PORT")))
steam_key = os.environ.get("STEAM_API_KEY")

a = Doer(SERVER_ADDRESS, steam_key)
a.start()
