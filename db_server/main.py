from dbserver import DBServer
from db_managers import PostgreSQLManager, SqliteManager


BIND_ADDRESS = ('localhost', 8000)
TELEGRAM_NOTIFIER_ADDRESS = ('localhost', 8001)
WEBSITE_URL = "http://localhost"

sqlite_manager = SqliteManager("db.db")

# database_values = ("ubuntu", "ubuntu", "localhost", "5432", "gtinfo")
# postgre_manager = PostgreSQLManager(*database_values)

a = DBServer(BIND_ADDRESS, WEBSITE_URL, sqlite_manager, TELEGRAM_NOTIFIER_ADDRESS)
a.premium_users_ids = [
            # here you can specify steam ids to track
        ]
a.start()
