import json
import datetime as dt
import socket
from time import sleep
from dataclasses import dataclass
from managers import DataManager
import threading
from enum import Enum, auto
from gtinfo_requests import *
from binary_functions import *


class UserTiers(Enum):
    basic = auto()
    premium = auto()


@dataclass
class LastRunTimestamps:
    basic: int
    premium: int
    update: int


@dataclass
class DoerSettings:
    basic_freq: int
    premium_freq: int
    update_freq: int


# decorator to check execution time (for users check only)
def time_check(f):
    def wrapper(self, users_tier):
        time_limit = 0
        if users_tier == UserTiers.basic:
            time_limit = self.settings.basic_freq
        elif users_tier == UserTiers.premium:
            time_limit = self.settings.premium_freq
        start_time = dt.datetime.utcnow()
        res = f(self, users_tier)
        time_delta = (dt.datetime.utcnow() - start_time).seconds
        if time_delta > time_limit:
            print(f"WARNING! {users_tier.name} checking takes too long ({time_delta}s > {time_limit}s)")
        return res
    return wrapper


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
        self.settings = DoerSettings(5, 5, 5)
        self.basic_user_ids = []
        self.premium_user_ids = []
        self.data_manager = DataManager(self)
        self.last_runs = LastRunTimestamps(0, 0, 0)
        self.data_to_send = []

        self.is_working = True

    # returns socket if db server operational, else None
    def try_to_connect(self):
        sock = socket.socket()
        sock.settimeout(5)
        try:
            sock.connect(self.db_server_address)
            if not self.db_operational:
                print(f"DB is operational since {dt.datetime.utcnow()} utc")
                self.db_operational = True
            return sock
        except (ConnectionRefusedError, socket.timeout, OSError) as ex:
            if self.db_operational:
                print(f"DB is not operational since {dt.datetime.utcnow()} utc ({ex})")
                self.db_operational = False

    def send_request(self, request):
        if not (sock := self.try_to_connect()):
            return make_request(GTInfoResponseTypes.no_connection, 0)
        send_msg(sock, json.dumps(request))
        if not (response := recv_msg(sock)):
            return make_request(GTInfoResponseTypes.no_response, 0)
        sock.close()
        response = json.loads(response)
        return response

    def quick_request(self, request_type, data):
        return read_request(self.send_request(make_request(request_type, data)))

    # update users list
    def apply_users(self, new_basic_user_ids, new_premium_user_ids):
        print(f"Applied {new_basic_user_ids}, {new_premium_user_ids} users")
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
        response_code, response_data = self.quick_request(GTInfoRequestTypes.doer_settings, 0)
        if response_code == GTInfoResponseTypes.ok:
            self.apply_settings(response_data)

        if not self.is_set_up:  # all users
            response_code, response_data = self.quick_request(GTInfoRequestTypes.doer_users, 0)
            if response_code == GTInfoResponseTypes.ok:
                self.apply_users(response_data["basic_user_ids"], response_data["premium_user_ids"])
                self.is_set_up = True
        else:  # all users if changed
            response_code, response_data = self.quick_request(GTInfoRequestTypes.doer_users_if_changed, 0)
            if response_code == GTInfoResponseTypes.ok:
                if response_data["changed"]:
                    self.apply_users(response_data["basic_user_ids"], response_data["premium_user_ids"])

    # send user activity objects to db server if there any
    def send_data_to_send(self):
        if not self.data_to_send:
            return

        data = {"user_online_activity_objects": self.data_to_send}
        response_code, response_data = self.quick_request(GTInfoRequestTypes.doer_new_user_online_activity_object, data)
        if response_code == GTInfoResponseTypes.ok:
            self.data_to_send = []

    # ask data manager for users and send data to db server
    @time_check
    def check_users(self, users_tier):
        if not self.is_set_up:
            return

        if users_tier == UserTiers.basic:
            self.data_to_send += self.data_manager.check_basic_users()
        elif users_tier == UserTiers.premium:
            self.data_to_send += self.data_manager.check_premium_users()

        self.send_data_to_send()

    def start(self):
        print("Doer starting... (1)")
        (data_collection := threading.Thread(target=self.start_data_collection)).start()
        (console := threading.Thread(target=self.start_console)).start()

        data_collection.join()
        console.join()

    def stop(self):
        print("Stopping execution...")
        self.is_working = False

    def start_data_collection(self):
        print("Data collection active")
        while self.is_working:
            current_timestamp = dt.datetime.utcnow().timestamp()
            if self.last_runs.update + self.settings.update_freq <= current_timestamp:
                self.last_runs.update = current_timestamp
                self.check_updates()
            if self.last_runs.basic + self.settings.basic_freq <= current_timestamp:
                self.last_runs.basic = current_timestamp
                self.check_users(UserTiers.basic)
            if self.last_runs.premium + self.settings.premium_freq <= current_timestamp:
                self.last_runs.premium = current_timestamp
                self.check_users(UserTiers.premium)
            sleep(1)
        print("Data collection stopped")

    def start_console(self):
        print("Console active. Type \"stop\" to stop")
        while self.is_working:
            command = input()
            if command == "stop":
                self.stop()
        print("Console stopped")
