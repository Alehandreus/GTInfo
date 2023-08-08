from db_server import DBServer
from db_managers import PostgreSQLManager, SqliteManager
import os

# from dotenv import load_dotenv
# load_dotenv()

BIND_ADDRESS = (os.environ.get("BIND_HOST"), int(os.environ.get("BIND_PORT")))
WEBSITE_URL = f"http://{os.environ.get('WEBSITE_HOST')}:{os.environ.get('WEBSITE_PORT')}"

database_values = (
    os.environ.get("SQL_USER"),
    os.environ.get("SQL_PASSWORD"),
    os.environ.get("SQL_HOST"),
    os.environ.get("SQL_PORT"),
    os.environ.get("SQL_DATABASE"),
)

postgre_manager = PostgreSQLManager(*database_values)

TELEGRAM_NOTIFIER_ADDRESS = (os.environ.get("TGNOTIFIER_HOST"), int(os.environ.get("TGNOTIFIER_PORT")))

a = DBServer(BIND_ADDRESS, WEBSITE_URL, postgre_manager, TELEGRAM_NOTIFIER_ADDRESS)
a.start()
