from enum import Enum, auto


class RequestTypes(int, Enum):
    doer_settings = auto()
    doer_users = auto()
    doer_users_if_changed = auto()
    doer_new_user_online_activity_object = auto()
    db_server_users = auto()


class ResponseTypes(int, Enum):
    ok = auto()
    no_such_command = auto()
    no_response = auto()
