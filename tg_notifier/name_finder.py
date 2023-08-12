import datetime as dt
import requests
from bs4 import BeautifulSoup
import json


class NameFinder:
    def __init__(self):
        self.appnames = dict()
        self.appnames_update = 0

        self.usernames = dict()
        self.usernames_update = 0

    def get_appname(self, appid):
        current_timestamp = dt.datetime.utcnow().timestamp()
        if current_timestamp - self.appnames_update >= 24 * 60 * 60:
            self.update_appnames()
            self.appnames_update = current_timestamp

        if (appname := self.appnames.get(appid, None)) is None:
            if (appname := self.parse_appname(appid)) is None:
                return f"unknown game {appid}"
            self.appnames[appid] = appname
        return appname

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

    def update_appnames(self):
        try:
            resp = requests.get("https://api.steampowered.com/ISteamApps/GetAppList/v2/")
            resp = json.loads(resp.text)
            self.appnames = {game["appid"]: game["name"] for game in resp["applist"]["apps"]}
        except Exception as e:
            print(f"Failed to get all appnames list: {e}")

    def get_username(self, steamid):
        current_timestamp = dt.datetime.utcnow().timestamp()
        if current_timestamp - self.usernames_update >= 24 * 60 * 60:
            self.update_usernames()
            self.usernames_update = current_timestamp

        if (username := self.usernames.get(steamid, None)) is None:
            if (username := self.parse_username(steamid)) is None:
                return f"unknown user {steamid}"
            self.usernames[steamid] = username
        return username

    @staticmethod
    def parse_username(steamid):
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

    def update_usernames(self):
        for steamid, username in self.usernames.items():
            if (new_username := self.parse_username(steamid)) is not None and new_username != username:
                self.usernames[steamid] = new_username
