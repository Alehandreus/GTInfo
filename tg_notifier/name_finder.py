import datetime as dt
import requests
from bs4 import BeautifulSoup
import json


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