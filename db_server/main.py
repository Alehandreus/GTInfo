from dbserver import DBServer
from notifiers import TelegramNotifier


DOER_ADDRESS = ('localhost', 8686)
database_values = ("postgres", "postgres", "localhost", "5432", "gtinfo")

telegram_notifier = TelegramNotifier(
    "",
    [

    ]
)

a = DBServer(DOER_ADDRESS, database_values, telegram_notifier)
a.start()
