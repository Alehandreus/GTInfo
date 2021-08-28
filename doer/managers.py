from concurrent.futures import as_completed
from requests_futures.sessions import FuturesSession
import requests
import json
import datetime as dt
import traceback


# one manager for each user
# requires a function to get recent playtimes
class BasicUserManager:
    def __init__(self, user_id, get_latest_games_function):
        self.user_id = user_id
        self.last_game = None  # None if user wasn't playing during last check and app id if was
        self.start_timestamp = None
        self.get_latest_games_function = get_latest_games_function

    # data param is dict with app ids as keys and playtimes as values
    # if end of game session detected, it is added to result data
    def analyze_data(self, data, current_timestamp):
        result_data = []  # list of tracked user objects to return
        if current_timestamp == 0:  # timestamp when request was sent
            current_timestamp = dt.datetime.utcnow().timestamp()

        current_game = data.get("gameid", None)
        if current_game:
            current_game = int(current_game)

        if current_game != self.last_game:
            if self.last_game is not None:
                resp = self.get_latest_games_function(self.user_id)
                if resp != {}:
                    total_played = resp["appid"] / 3600

                    result_data = [{
                        "tracked_user": self.user_id,
                        "started_playing_timestamp": int(self.start_timestamp),
                        "ended_playing_timestamp": int(current_timestamp),
                        "game_id": self.last_game,
                        "total_played": total_played
                    }]
            else:
                self.start_timestamp = current_timestamp
        self.last_game = current_game
        return result_data


# like basic manager
# requires all user playtimes at start
class PremiumUserManager:
    def __init__(self, userid, all_playtimes):
        self.user_id = userid
        self.last_known_playtimes = all_playtimes
        self.sessions_start_playtimes = {}  # { app_id: [start_playtime, last_check_timestamp], }

    def analyze_data(self, data, current_timestamp=0):
        result_data = []  # list of tracked user objects to return
        if current_timestamp == 0:  # timestamp when request was sent
            current_timestamp = dt.datetime.utcnow().timestamp()

        for game in data:
            app_id, current_playtime = game["appid"], game["playtime_forever"] * 60  # all play times in seconds

            last_playtime = self.last_known_playtimes.get(app_id, 0)
            if last_playtime != current_playtime:  # if playtime changed
                playtime_diff = (current_playtime - last_playtime)

                # session end guarantee
                if playtime_diff < 1800:
                    if app_id in self.sessions_start_playtimes.keys():
                        session_playtime_diff = current_playtime - self.sessions_start_playtimes.pop(app_id)[0]
                        start_timestamp = current_timestamp - session_playtime_diff
                    else:
                        start_timestamp = current_timestamp - playtime_diff
                    mini_data = {
                        "tracked_user": self.user_id,
                        "started_playing_timestamp": int(start_timestamp),
                        "ended_playing_timestamp": int(current_timestamp),
                        "game_id": app_id,
                        "total_played": round(current_playtime / 3600, 2)
                    }
                    result_data.append(mini_data)

                #      regular steam update      steam bug, lets interpret as regular update
                elif (playtime_diff == 1800) or (playtime_diff > 1800 and last_playtime != 0):
                    if app_id in self.sessions_start_playtimes.keys():
                        self.sessions_start_playtimes[app_id][1] = current_timestamp
                    else:
                        self.sessions_start_playtimes[app_id] = [last_playtime, current_timestamp]

                # new game discovered, lets do nothing
                elif playtime_diff > 1800 and last_playtime == 0:
                    pass

            self.last_known_playtimes[app_id] = current_playtime

        # additional checks
        # if last session update was more than 50 minutes ago, end it
        for app_id, values in self.sessions_start_playtimes.copy().items():
            start_playtime, last_check_timestamp = values[0], values[1]
            if abs(current_timestamp - last_check_timestamp) > 50 * 60:  # 50 minutes
                total_playtime_diff = self.last_known_playtimes[app_id] - start_playtime
                start_timestamp = last_check_timestamp - total_playtime_diff

                mini_data = {
                    "tracked_user": self.user_id,
                    "started_playing_timestamp": int(start_timestamp),
                    "ended_playing_timestamp": int(last_check_timestamp),
                    "game_id": app_id,
                    "total_played": round(self.last_known_playtimes[app_id] / 3600, 2)
                }
                result_data.append(mini_data)
                self.sessions_start_playtimes.pop(app_id)

        return result_data


class DataManager:
    def __init__(self, doer_class):
        self.master = doer_class
        self.basic_users_managers = {user_id: BasicUserManager(user_id, self.get_recent_playtimes) for user_id in self.master.basic_user_ids}
        self.premium_users_managers = {user_id: PremiumUserManager(user_id, self.get_all_playtimes(user_id)) for user_id in self.master.premium_user_ids}

    def get_recent_playtimes(self, user_id):
        url = f"http://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/?key={self.master.steam_key}&steamid={user_id}&include_played_free_games=1"
        resp = requests.get(url)

        if resp.status_code != 200:
            print(f"Request failed. Status code: {resp.status_code}")
            return {}

        try:
            resp = json.loads(resp.text)["response"]
            if resp["total_count"] != 0:
                res = {game["appid"]: game["playtime_forever"] * 60 for game in resp["games"]}
                return res
        except KeyError:
            traceback.print_exc()
        return {}

    def get_all_playtimes(self, user_id):
        url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={self.master.steam_key}&steamid={user_id}&include_played_free_games=1"
        resp = requests.get(url)

        if resp.status_code != 200:
            return {}

        try:
            resp = json.loads(resp.text)["response"]
            if resp["game_count"] != 0:
                res = {game["appid"]: game["playtime_forever"] * 60 for game in resp["games"]}
                return res | self.get_recent_playtimes(user_id)
        except KeyError:
            traceback.print_exc()
        return {}

    # delete old user managers, create new
    def update_user_ids(self, new_basic_user_ids, new_premium_user_ids):
        new_basic_user_ids, new_premium_user_ids = set(new_basic_user_ids), set(new_premium_user_ids)
        old_basic_user_ids, old_premium_user_ids = set(self.master.basic_user_ids), set(self.master.premium_user_ids)

        for removed_userid in old_basic_user_ids - new_basic_user_ids:
            del self.basic_users_managers[removed_userid]
        for additional_userid in new_basic_user_ids - old_basic_user_ids:
            self.basic_users_managers[additional_userid] = BasicUserManager(additional_userid, self.get_recent_playtimes)

        for removed_userid in old_premium_user_ids - new_premium_user_ids:
            del self.basic_users_managers[removed_userid]
        for additional_userid in new_premium_user_ids - old_premium_user_ids:
            self.premium_users_managers[additional_userid] = PremiumUserManager(additional_userid, self.get_all_playtimes(additional_userid))

    def check_basic_users(self):
        result_data = []
        basic_users_count = len(self.master.basic_user_ids)
        urls = []
        for i in range(0, basic_users_count, 100):
            start = i
            end = i + 100 if i + 100 < basic_users_count else basic_users_count

            users_range = ",".join([str(i) for i in self.master.basic_user_ids[start:end]])
            new_url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={self.master.steam_key}&steamids={users_range}"
            urls.append(new_url)
        with FuturesSession() as session:
            futures = [session.get(url) for url in urls]
            for future in as_completed(futures):
                response = future.result()
                if response.status_code == 200:
                    response = json.loads(response.text)
                    for player in response["response"]["players"]:
                        result_data += self.basic_users_managers[int(player["steamid"])].analyze_data(player, dt.datetime.utcnow().timestamp())
        return result_data

    def check_premium_users(self):
        url_template = "http://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/?key={}&steamid={}&include_played_free_games=1"
        urls = [url_template.format(self.master.steam_key, user_id) for user_id in self.master.premium_user_ids]
        result_data = []
        with FuturesSession() as session:
            futures = [session.get(url) for url in urls]
            for future in as_completed(futures):
                if not (future._result):  # wut
                    continue

                # responses come in random order so we have to somehow get steam id from this result
                steam_id = self.extract_steamid_from_url(future._result.url)  # see below
                response = future.result()

                if not (response.status_code == 200):  # first response check
                    continue

                try:  # trying to parse to dict
                    response = json.loads(response.text)["response"]
                except json.decoder.JSONDecodeError as ex:  # probably request futures messed up
                    continue

                if not ("games" in response.keys()):  # check if response is not empty
                    continue  # response is empty, steam bug perhaps

                # finally
                result_data += self.premium_users_managers[steam_id].analyze_data(response["games"], dt.datetime.utcnow().timestamp())
        return result_data

    @staticmethod
    def extract_steamid_from_url(url):
        ix = url.find("steamid=") + 8
        return int(url[ix:ix + 17])
