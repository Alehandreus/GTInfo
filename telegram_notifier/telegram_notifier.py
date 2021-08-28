import telebot
import datetime as dt
import requests
from bs4 import BeautifulSoup
import json
import threading
import socket
from binary_functions import *


# add 3 hours to date lol
def f(x):
    return dt.datetime.strftime(dt.datetime.fromtimestamp(x) + dt.timedelta(hours=3), format="%H:%M")


class SimpleTelegramNotifier:
    def __init__(self, bind_address, token, tracked_users, notified_users):
        self.bot = telebot.AsyncTeleBot(token)
        self.name_finder = NameFinder()

        self.BIND_ADDRESS = bind_address

        self.tracked_users = tracked_users
        self.notified_users = notified_users

        self.is_working = True

    def start(self):
        print("Telegram notifier starting...")

        socket_thread = threading.Thread(target=self.start_socket)
        socket_thread.start()

        console_thread = threading.Thread(target=self.start_console)
        console_thread.start()

        socket_thread.join()
        console_thread.join()

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

    def notify(self, user_online_activity_objects):
        print(user_online_activity_objects)
        for user_online_activity_object in user_online_activity_objects:
            if int(user_online_activity_object['tracked_user']) in self.tracked_users:
                for notified_user in self.notified_users:
                    data = user_online_activity_object
                    s = f"" \
                        f"{self.name_finder.get_username(data['tracked_user'])} was playing " \
                        f"{self.name_finder.get_appname(data['game_id'])} " \
                        f"({f(data['started_playing_timestamp'])} — {f(data['ended_playing_timestamp'])})"
                    self.bot.send_message(notified_user, s)

    def serve_request_new_user_online_activity_objects(self, data):
        user_online_activity_objects = data["user_online_activity_objects"]
        self.notify(user_online_activity_objects)
        return {}


do_smth_with_request_dict = {
    "new_user_online_activity_objects": SimpleTelegramNotifier.serve_request_new_user_online_activity_objects,
}


class NameFinder:
    def __init__(self):
        self.all_appnames = None

    @staticmethod
    def get_all_appnames():
        try:
            resp = requests.get("https://api.steampowered.com/ISteamApps/GetAppList/v2/")
            resp = json.loads(resp.text)
            return {game["appid"]: game["name"] for game in resp["applist"]["apps"]}
        except Exception as e:
            print(f"Failed to get all appnames list: {e}")
        return None

    def get_appname(self, appid):
        appname = self.parse_appname(appid)
        if appname is not None:
            return appname

        current_timestamp = dt.datetime.utcnow().timestamp()
        if self.last_update is None or \
                self.all_appnames is None or \
                current_timestamp - self.last_update >= 86400:  # update every 24 hours

            new_all_appnames = self.get_all_appnames()
            if new_all_appnames is not None:
                self.all_appnames = new_all_appnames
                self.last_update = current_timestamp

        if self.all_appnames is None:
            return f"unknown game {appid}"

        return self.all_appnames.get(appid, f"unknown game {appid}")

    @staticmethod
    def parse_appname(gameid):
        url = "https://store.steampowered.com/app/" + str(gameid)
        getresponse = requests.get(url)
        if getresponse.status_code != 200:
            return None
        soup = BeautifulSoup(getresponse.content, 'html.parser')
        a = soup.find("div", class_="apphub_AppName")
        if a is None:
            return None
        game_name = a.text
        return game_name

    @staticmethod
    def get_username(steamid):
        url = "https://steamcommunity.com/profiles/" + str(steamid)
        getresponse = requests.get(url)
        if getresponse.status_code != 200:
            return None
        soup = BeautifulSoup(getresponse.content, 'html.parser')
        a = soup.find("span", class_="actual_persona_name")
        if a is None:
            return None
        username = a.text
        return username