from enum import Enum, auto


class GTInfoRequestTypes(int, Enum):
    doer_settings = auto()
    doer_users = auto()
    doer_users_if_changed = auto()
    doer_new_user_online_activity_object = auto()
    db_server_users = auto()
    web_user_online_activity_objects = auto()
    web_users_with_data = auto()
    web_games_with_data = auto()
    incorrect = auto()


class GTInfoResponseTypes(int, Enum):
    ok = auto()
    error = auto()
    no_connection = auto()
    no_such_command = auto()
    no_response = auto()


class DBManagerResponseTypes(int, Enum):
    ok = auto()
    error = auto()


def make_request(request_type, data):
    return {"type": request_type, "data": data}


def read_request(request):
    if "type" not in request.keys() or "data" not in request.keys():
        return GTInfoResponseTypes.incorrect, 0
    return request["type"], request["data"]
