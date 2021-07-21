import json
import datetime as dt
import socket
from time import sleep
from dataclasses import dataclass
from binary_functions import *
from managers import DataManager
import threading


@dataclass
class LastRunTimestamps:
    basic: int
    premium: int
    update: int


@dataclass
class Settings:
    basic_freq: int
    premium_freq: int
    update_freq: int


# Doer interacts with db server:
#   settings updates
#   user lists updates
#   send data from data manager
class Doer:
    def __init__(self, db_server_address, steam_key):
        self.is_set_up = False
        self.db_operational = True  # db is anyway checked during setup
        self.db_server_address = db_server_address
        self.steam_key = steam_key
        self.settings = Settings(5, 5, 5)
        self.basic_user_ids = []
        self.premium_user_ids = []
        self.data_manager = DataManager(self)
        self.last_runs = LastRunTimestamps(0, 0, 0)
        self.is_working = True

    # returns socket if db server operational, else False
    def try_to_connect(self):
        sock = socket.socket()
        try:
            sock.connect(self.db_server_address)
            if not self.db_operational:
                print(f"DB is operational since {dt.datetime.utcnow()} utc")
            self.db_operational = True
            return sock
        except ConnectionRefusedError:
            if self.db_operational:
                print(f"DB is not operational since {dt.datetime.utcnow()} utc")
            self.db_operational = False
            return False

    # update users list
    def apply_users(self, new_basic_user_ids, new_premium_user_ids):
        self.data_manager.update_user_ids(new_basic_user_ids, new_premium_user_ids)
        self.basic_user_ids = new_basic_user_ids
        self.premium_user_ids = new_premium_user_ids

    # update settings
    def apply_settings(self, settings_dict):
        self.settings.basic_freq = settings_dict.get("basic_user_request_freq", self.settings.basic_freq)
        self.settings.premium_freq = settings_dict.get("premium_user_request_freq", self.settings.basic_freq)
        self.settings.update_freq = settings_dict.get("settings_update_freq", self.settings.basic_freq)

    # update from db server
    def check_updates(self):
        sock = self.try_to_connect()
        if not sock:
            return

        # if first time
        if not self.is_set_up:
            # setting up
            req_str = json.dumps({"command": "full_settings"})
            send_msg(sock, req_str)
            response = json.loads(recv_msg(sock))
            self.apply_settings(response["data"])
            sock.close()

            sock = socket.socket()
            sock.connect(self.db_server_address)
            req_str = json.dumps({"command": "full_users"})
            send_msg(sock, req_str)
            response = json.loads(recv_msg(sock))
            self.apply_users(response["data"]["basic_user_ids"], response["data"]["premium_user_ids"])
            sock.close()

            self.is_set_up = True
        else:
            # updating settings
            req_str = json.dumps({"command": "full_settings"})
            send_msg(sock, req_str)
            response = json.loads(recv_msg(sock))
            self.apply_settings(response["data"])
            sock.close()

            # updating users
            sock = socket.socket()
            sock.connect(self.db_server_address)
            req_str = json.dumps({"command": "users_if_changed"})
            send_msg(sock, req_str)
            response = json.loads(recv_msg(sock))
            sock.close()
            if response["changed"]:
                self.apply_users(response["data"]["basic_user_ids"], response["data"]["premium_user_ids"])

    # send user activity objects to db server
    def send_data(self, data):
        sock = self.try_to_connect()
        if not sock:
            return

        req = {"command": "new_user_online_activity_objects", "user_online_activity_objects": data}
        req_str = json.dumps(req)
        send_msg(sock, req_str)
        sock.close()

    # ask data manager for basic users and send data to db server
    def check_basic_users(self):
        if not self.is_set_up:
            return
        time_1 = dt.datetime.now()

        if self.db_operational:
            new_data = self.data_manager.check_basic_users()
            if new_data:
                print(new_data)
                self.send_data(new_data)

        time_delta = (dt.datetime.now() - time_1).seconds
        if time_delta > self.settings.basic_freq:
            print(f"WARNING! It takes too long! ({time_delta}s > {self.settings.basic_freq}s)")

    # ask data manager for premium users and send data to db server
    def check_premium_users(self):
        if not self.is_set_up:
            return
        time_1 = dt.datetime.utcnow()

        if self.db_operational:
            new_data = self.data_manager.check_premium_users()
            if new_data:
                print(new_data)
                self.send_data(new_data)

        time_delta = (dt.datetime.utcnow() - time_1).seconds
        if time_delta > self.settings.premium_freq:
            print(f"WARNING! It takes too long! ({time_delta}s > {self.settings.premium_freq}s)")

    def start(self):
        print("Doer starting...")
        data_collection = threading.Thread(target=self.start_data_collection)
        data_collection.start()
        console = threading.Thread(target=self.start_console)
        console.start()
        data_collection.join()
        console.join()

    def start_data_collection(self):
        print("Data collection active")
        while self.is_working:
            current_timestamp = dt.datetime.utcnow().timestamp()
            if self.last_runs.update + self.settings.update_freq <= current_timestamp:
                self.last_runs.update = current_timestamp
                self.check_updates()
            if self.last_runs.basic + self.settings.basic_freq <= current_timestamp:
                self.last_runs.basic = current_timestamp
                self.check_basic_users()
            if self.last_runs.premium + self.settings.premium_freq <= current_timestamp:
                self.last_runs.premium = current_timestamp
                self.check_premium_users()
            sleep(1)

    def start_console(self):
        print("Console active. Type \"stop\" to stop")
        while self.is_working:
            command = input()
            if command == "stop":
                print("Stopping execution...")
                self.is_working = False
