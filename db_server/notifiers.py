import telebot
import datetime as dt
import requests
from bs4 import BeautifulSoup


# add 3 hours to date
def f(x):
    return dt.datetime.strftime(dt.datetime.fromtimestamp(x) + dt.timedelta(hours=3), format="%H:%M")


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


def get_appname(gameid):
    if gameid == 480:
        return "Spacewar"  # wut
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


class TelegramNotifier:
    def __init__(self, token, chat_ids):
        self.token = token
        self.chat_ids = chat_ids
        self.bot = telebot.AsyncTeleBot(token)

    def notify(self, data):
        s = f"" \
            f"{get_username(data['tracked_user'])} was playing " \
            f"{get_appname(data['game_id'])} " \
            f"({f(data['started_playing_timestamp'])} — {f(data['ended_playing_timestamp'])})"
        self.send_text(s)

    def send_text(self, text):
        for chat_id in self.chat_ids:
            self.bot.send_message(chat_id, text, parse_mode='Markdown')
