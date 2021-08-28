import socket
import json
import requests
from binary_functions import *
import threading
from notifiers import SenderToTelegramNotifier


class DBServer:
    def __init__(self, bind_address, website_url, db_manager, telegram_notifier_address=None):
        self.basic_users_ids = []
        self.premium_users_ids = []
        self.db_manager = db_manager

        self.BIND_ADDRESS = bind_address
        self.WEBSITE_URL = website_url

        self.sender_to_telegram_notifier = None
        if telegram_notifier_address:
            self.sender_to_telegram_notifier = SenderToTelegramNotifier(telegram_notifier_address)

        self.users_changed = True
        self.is_working = True

        self.set_users()

    # send data about user online activity objects to telegram address
    def send_notification(self, data):
        if self.sender_to_telegram_notifier:
            self.sender_to_telegram_notifier.send_data(data)

    def start(self):
        print("DB server starting...")

        socket_thread = threading.Thread(target=self.start_socket)
        socket_thread.start()

        console = threading.Thread(target=self.start_console)
        console.start()

        socket_thread.join()
        console.join()

    def start_socket(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(self.BIND_ADDRESS)
        self.server_socket.listen()

        print('Socket active')
        while self.is_working:
            try:
                connection, address = self.server_socket.accept()
                data = json.loads(recv_msg(connection))
                resp_dict = do_smth_with_request_dict.get(data["command"], lambda a, b: {})(self, data)
                resp_str = json.dumps(resp_dict)
                send_msg(connection, resp_str)
                connection.close()
            except Exception as ex:
                print(ex)
        print("Socket stopped")

    def stop_socket(self):
        tempsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tempsocket.connect(self.BIND_ADDRESS)
        send_msg(tempsocket, json.dumps({"command": "nocommand"}))
        self.server_socket.close()

    def start_console(self):
        print("Console active. Type \"stop\" to stop")
        while self.is_working:
            command = input()
            if command == "stop":
                print("Stopping execution...")
                self.is_working = False
                self.stop_socket()
            if command == "backup":
                self.db_manager.create_backup_csv()
                print("csv backup created")

    def set_users(self):
        try:
            resp = requests.get(f"{self.WEBSITE_URL}/iu_api/tracked_user_object/?format=json", auth=requests.auth.HTTPBasicAuth('admin', 'rockpassword'))
        except Exception as ex:
            print(f"Warning! Failed to get tracked users from {self.WEBSITE_URL}")
            return

        resp = json.loads(resp.text)
        self.basic_users_ids = [el["steam_id"] for el in resp["results"]]
        while resp["next"]:
            resp = requests.get(f"{self.WEBSITE_URL}/iu_api/tracked_user_object/?format=json", auth=requests.auth.HTTPBasicAuth('admin', 'rockpassword'))
            resp = json.loads(resp.text)
            self.basic_users_ids += [el["steam_id"] for el in resp["results"]]

        self.premium_users_ids = []  # as far as i know, premium users api is not implemented yet

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
        self.send_notification(user_online_activity_objects)
        print(user_online_activity_objects)
        for user_online_activity_object in user_online_activity_objects:
            self.db_manager.add_play_interval(user_online_activity_object)
        return {}


do_smth_with_request_dict = {
        "full_settings": DBServer.serve_request_full_settings,
        "full_users": DBServer.serve_request_all_users,
        "users_if_changed": DBServer.serve_request_changed_users,
        "new_user_online_activity_objects": DBServer.serve_request_new_user_online_activity_objects,
    }
