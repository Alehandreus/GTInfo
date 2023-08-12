import socket
import json
import requests
from binary_functions import *
import threading
from notifiers import SenderToTelegramNotifier
import os
from dataclasses import dataclass, asdict
import datetime as dt
from time import sleep
from gtinfo_requests import *
import re
from collections import defaultdict


@dataclass
class LastRunTimestamps:
    users_retrieval: int


@dataclass
class DBServerSettings:
    users_retrieval_freq: int


@dataclass
class DoerSettings:
    basic_freq: int
    premium_freq: int
    update_freq: int


class DBServer:
    def __init__(self, bind_address, website_url, db_manager, telegram_notifier_address=None):
        self.basic_users_ids = []
        self.premium_users_ids = []

        self.new_basic_users_ids = []
        self.new_premium_users_ids = []

        self.db_manager = db_manager
        self.request_servant = RequestServant(self)

        self.BIND_ADDRESS = bind_address
        self.server_socket = None

        self.WEBSITE_URL = website_url
        self.SUPERUSER_USER = os.environ.get("SUPERUSER_USER")
        self.SUPERUSER_PASSWORD = os.environ.get("SUPERUSER_PASSWORD")
        self.superuser_auth = requests.auth.HTTPBasicAuth(self.SUPERUSER_USER, self.SUPERUSER_PASSWORD)

        self.sender_to_telegram_notifier = None
        if telegram_notifier_address is not None:
            self.sender_to_telegram_notifier = SenderToTelegramNotifier(telegram_notifier_address)

        self.settings = DBServerSettings(50)
        self.doer_settings = DoerSettings(10, 5, 15)
        self.last_runs = LastRunTimestamps(0)

        self.users_changed = True
        self.is_working = True

        self.retrieve_users()

    # send data about user online activity objects to telegram address
    def send_notification(self, data):
        if self.sender_to_telegram_notifier is not None:
            self.sender_to_telegram_notifier.send_data(data)

    def start(self):
        print("DB server starting...")

        (socket_thread := threading.Thread(target=self.start_socket)).start()
        (users_update_thread := threading.Thread(target=self.start_users_update)).start()
        (console_thread := threading.Thread(target=self.start_console)).start()

        socket_thread.join()
        console_thread.join()
        users_update_thread.join()

    def start_users_update(self):
        print("Data collection active")
        while self.is_working:
            current_timestamp = dt.datetime.utcnow().timestamp()
            if self.last_runs.users_retrieval + self.settings.users_retrieval_freq <= current_timestamp:
                self.last_runs.users_retrieval = current_timestamp
                self.retrieve_users_new()
            sleep(1)
        print("Users update stopped")

    def start_socket(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(self.BIND_ADDRESS)
        self.server_socket.listen()

        print('Socket active')
        while self.is_working:
            connection, address = self.server_socket.accept()
            request_raw = recv_msg(connection)
            try:
                request_dict = json.loads(request_raw)
                resp_dict = self.request_servant.serve_request(*read_request(request_dict))
                send_msg(connection, json.dumps(resp_dict))
            except (ValueError, TypeError):
                print(f"Incorrect request: {request_raw}")
            except Exception as ex:
                print(f"Error: {ex}")
            connection.close()
        print("Socket stopped")

    def stop_socket(self):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(self.BIND_ADDRESS)
        self.server_socket.close()

    def start_console(self):
        print("Console active. Type \"stop\" to stop")
        while self.is_working:
            command = input()
            if re.match(r'stop', command):
                print("Stopping execution...")
                self.is_working = False
                self.stop_socket()
            elif re.match(r'backup', command):
                self.db_manager.create_backup_csv()
                print("csv backup created")
            elif res := re.match(r'addtrackeduser (\d*) (basic|premium)', command):
                userid, premiumness = res.groups()
                userid = int(userid)
                if premiumness == "basic":
                    self.basic_users_ids.append(userid)
                else:
                    self.premium_users_ids.append(userid)
                self.users_changed = True
                print(f"Added user {userid} ({premiumness})")

    def retrieve_users_new(self):
        self.new_basic_users_ids = []
        self.new_premium_users_ids = []

        try:
            resp = requests.get(f"{self.WEBSITE_URL}/tracked_users")
        except Exception as ex:
            print(f"Warning! Failed to connect to {self.WEBSITE_URL} ({ex})")
            return

        try:
            resp = json.loads(resp.text)
        except (ValueError, TypeError) as ex:
            print(f"Failed to retrieve users: {ex}")
            return

        for el in resp["users"]:
            self.new_premium_users_ids.append(int(el))

        if self.new_basic_users_ids != self.basic_users_ids or self.new_premium_users_ids != self.premium_users_ids:
            self.users_changed = True
            print(f"Users from {self.WEBSITE_URL}: {self.new_basic_users_ids}, {self.new_premium_users_ids}")

        self.basic_users_ids = self.new_basic_users_ids
        self.premium_users_ids = self.new_premium_users_ids

    def retrieve_users(self):
        self.new_basic_users_ids = []
        self.new_premium_users_ids = []

        if not (resp := self.retrieve_users_page(f"{self.WEBSITE_URL}/tracked_users")):
            return

        while resp["next"]:
            if not (resp := self.retrieve_users_page(resp["next"])):
                return

        if self.new_basic_users_ids != self.basic_users_ids or self.new_premium_users_ids != self.premium_users_ids:
            self.users_changed = True

        print(f"Users from {self.WEBSITE_URL}: {self.new_basic_users_ids}, {self.new_premium_users_ids}")

        self.basic_users_ids = self.new_basic_users_ids
        self.premium_users_ids = self.new_premium_users_ids

    def retrieve_users_page(self, url):
        try:
            resp = requests.get(url, auth=self.superuser_auth)
        except Exception as ex:
            print(f"Warning! Failed to connect to {self.WEBSITE_URL} ({ex})")
            return

        try:
            resp = json.loads(resp.text)
        except (ValueError, TypeError) as ex:
            print(f"Failed to retrieve users: {ex}")
            return

        if resp.get("count", -1) == -1:
            print(f"Warning! Failed to get tracked users from {self.WEBSITE_URL}")
            return

        for el in resp["results"]:
            if el["is_premium"]:
                self.new_premium_users_ids.append(el["steam_id"])
            else:
                self.new_basic_users_ids.append(el["steam_id"])

        return resp


class RequestServant:
    def __init__(self, db_server):
        self.db_server = db_server
        self.request_servants = {
            GTInfoRequestTypes.doer_users: self.serve_doer_users,
            GTInfoRequestTypes.doer_users_if_changed: self.serve_doer_users_if_changed,
            GTInfoRequestTypes.doer_settings: self.serve_doer_settings,
            GTInfoRequestTypes.doer_new_user_online_activity_object: self.serve_doer_new_user_online_activity_object,
            GTInfoRequestTypes.web_user_online_activity_objects: self.web_user_online_activity_objects,
            GTInfoRequestTypes.web_users_with_data: self.web_users_with_data,
            GTInfoRequestTypes.web_games_with_data: self.web_games_with_data,
            GTInfoRequestTypes.most_played_users: self.most_played_users,
            GTInfoRequestTypes.most_played_games: self.most_played_games,
        }

    def serve_request(self, request_type, request_data):
        if servant := self.request_servants.get(request_type, None):
            return servant(request_data)

        return make_request(GTInfoResponseTypes.no_such_command, 0)

    def serve_doer_users(self, request_data):
        data = {
            "basic_user_ids": self.db_server.basic_users_ids,
            "premium_user_ids": self.db_server.premium_users_ids
        }
        self.db_server.users_changed = False
        return make_request(GTInfoResponseTypes.ok, data)

    def serve_doer_users_if_changed(self, request_data):
        data = {"changed": self.db_server.users_changed}
        if self.db_server.users_changed:
            data["basic_user_ids"] = self.db_server.basic_users_ids
            data["premium_user_ids"] = self.db_server.premium_users_ids
            self.db_server.users_changed = False
        return make_request(GTInfoResponseTypes.ok, data)

    def serve_doer_settings(self, request_data):
        settings = self.db_server.doer_settings
        return make_request(GTInfoResponseTypes.ok, asdict(settings))

    def serve_doer_new_user_online_activity_object(self, request_data):
        user_online_activity_objects = request_data["user_online_activity_objects"]
        self.db_server.send_notification(user_online_activity_objects)
        print(user_online_activity_objects)
        for user_online_activity_object in user_online_activity_objects:
            db_manager_response = self.db_server.db_manager.add_user_online_activity_object(user_online_activity_object)
            response_code, response_data = read_request(db_manager_response)
            if response_code != DBManagerResponseTypes.ok:
                return make_request(GTInfoResponseTypes.error, 0)
        return make_request(GTInfoResponseTypes.ok, 0)

    def web_user_online_activity_objects(self, request_data):
        db_manager_response = self.db_server.db_manager.get_user_online_activity_objects(request_data)
        response_code, response_data = read_request(db_manager_response)
        if response_code != DBManagerResponseTypes.ok:
            return make_request(GTInfoResponseTypes.error, 0)
        return make_request(GTInfoResponseTypes.ok, response_data)

    def most_played_users(self, request_data):
        # ["start_timestamp": 1, "end_timestamp": 2, "tracked_users": [1, 2, 3], "limit": 10]
        db_manager_response = self.db_server.db_manager.get_most_played_users(request_data)
        response_code, response_data = read_request(db_manager_response)
        if response_code != DBManagerResponseTypes.ok:
            return make_request(GTInfoResponseTypes.error, 0)
        return make_request(GTInfoResponseTypes.ok, response_data)

    def most_played_games(self, request_data):
        # ["start_timestamp": 1, "end_timestamp": 2, "tracked_users": [1, 2, 3], "limit": 10]
        db_manager_response = self.db_server.db_manager.get_most_played_games(request_data)
        response_code, response_data = read_request(db_manager_response)
        if response_code != DBManagerResponseTypes.ok:
            return make_request(GTInfoResponseTypes.error, 0)
        return make_request(GTInfoResponseTypes.ok, response_data)

    def web_users_with_data(self, request_data):
        db_manager_response = self.db_server.db_manager.get_users_with_data(request_data)
        response_code, response_data = read_request(db_manager_response)
        if response_code != DBManagerResponseTypes.ok:
            return make_request(GTInfoResponseTypes.error, 0)
        return make_request(GTInfoResponseTypes.ok, response_data)

    def web_games_with_data(self, request_data):
        db_manager_response = self.db_server.db_manager.get_games_with_data(request_data)
        response_code, response_data = read_request(db_manager_response)
        if response_code != DBManagerResponseTypes.ok:
            return make_request(GTInfoResponseTypes.error, 0)
        return make_request(GTInfoResponseTypes.ok, response_data)
