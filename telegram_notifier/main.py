from telegram_notifier import SimpleTelegramNotifier


BIND_ADDRESS = ('localhost', 8001)

token = ""  # telegram token

tracked_users = [
            # list of steam 64 ids
        ]

notified_users = [
        # list of telegram chat ids
    ]

a = SimpleTelegramNotifier(BIND_ADDRESS, token, tracked_users, notified_users)
a.start()
