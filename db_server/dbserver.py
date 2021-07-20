import socket
import json
import requests
from binary_functions import *
from db_managers import PostgreSQLManager


class DBServer:
    def __init__(self, doer_address, database_values, telegram_notifier):
        self.basic_users_ids = []
        self.premium_users_ids = []
        self.db_manager = PostgreSQLManager(*database_values)
        self.users_changed = True
        self.DOER_ADDRESS = doer_address
        self.telegram_notifier = telegram_notifier
        self.telegram_notifier.set_current_db(self.db_manager)

        # updating users is not implemented
        # self.set_users()

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(self.DOER_ADDRESS)
        server_socket.listen()

        print('server is running, please, press ctrl+c to stop')
        while True:
            try:
                connection, address = server_socket.accept()
                data = json.loads(recv_msg(connection))
                resp_dict = do_smth_with_request_dict.get(data["command"], lambda a, b: {})(self, data)
                resp_str = json.dumps(resp_dict)
                send_msg(connection, resp_str)
                connection.close()
            except Exception as ex:
                print(ex)

    def set_users(self):
        resp = requests.get("http://127.0.0.1:8000/iu_api/tracked_user_object/?format=json", auth=requests.auth.HTTPBasicAuth('admin', 'rockpassword'))
        resp = json.loads(resp.text)
        self.basic_users_ids = [el["steam_id"] for el in resp["results"]]
        while resp["next"]:
            resp = requests.get("http://127.0.0.1:8000/iu_api/tracked_user_object/?format=json", auth=requests.auth.HTTPBasicAuth('admin', 'rockpassword'))
            resp = json.loads(resp.text)
            self.basic_users_ids += [el["steam_id"] for el in resp["results"]]
        self.premium_users_ids = []

    def serve_request_full_settings(self, data=None):
        settings = {
            "basic_user_request_freq": 10,
            "premium_user_request_freq": 5,
            "settings_update_freq": 15,
        }
        resp = {"data": settings}
        return resp

    def serve_request_all_users(self, data=None):
        users = {
            "basic_user_ids": self.basic_users_ids,
            "premium_user_ids": self.premium_users_ids
        }
        resp = {"data": users}
        self.users_changed = False
        return resp

    def serve_request_changed_users(self, data=None):
        resp = {"changed": self.users_changed}
        if self.users_changed:
            resp["data"] = {
                "basic_user_ids": self.basic_users_ids,
                "premium_user_ids": self.premium_users_ids
            }
        self.users_changed = False
        return resp

    def serve_request_new_user_online_activity_objects(self, data):
        user_online_activity_objects = data["user_online_activity_objects"]
        print(data)
        for user_online_activity_object in user_online_activity_objects:
            self.telegram_notifier.notify(user_online_activity_object)
            self.db_manager.add_play_interval(user_online_activity_object)
        return {}


do_smth_with_request_dict = {
        "full_settings": DBServer.serve_request_full_settings,
        "full_users": DBServer.serve_request_all_users,
        "users_if_changed": DBServer.serve_request_changed_users,
        "new_user_online_activity_objects": DBServer.serve_request_new_user_online_activity_objects,
    }
