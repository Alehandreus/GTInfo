from dbserver import DBServer
from db_managers import PostgreSQLManager


BIND_ADDRESS = ('localhost', 8000)
TELEGRAM_NOTIFIER_ADDRESS = ('localhost', 8001)

database_values = ("ubuntu", "ubuntu", "localhost", "5432", "gtinfo")
db_manager = PostgreSQLManager(*database_values)

a = DBServer(BIND_ADDRESS, db_manager, TELEGRAM_NOTIFIER_ADDRESS)
a.premium_users_ids = [
            # here you can specify steam ids to track
        ]
a.start()
