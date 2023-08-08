import os
import sqlite3
import psycopg2
import datetime as dt
from abc import ABC
import csv
from functools import wraps
from gtinfo_requests import DBManagerResponseTypes, GTInfoRequestTypes, make_request, read_request


def create_file_if_not_exists(filepath):
    if not os.path.isfile(filepath):
        with open(filepath, "w"):
            pass


def with_cursor(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        obj = args[0]

        try:
            conn = obj.db_module.connect(**obj.connection_dict)
            cursor = conn.cursor()
        except Exception as ex:
            print(f"Database connection failure: {ex}")
            obj.is_set_up = False
            return make_request(DBManagerResponseTypes.error, 0)

        if not obj.is_set_up:
            try:
                obj.create_tables.__wrapped__(obj, cursor)
                conn.commit()
                obj.is_set_up = True
            except Exception as ex:
                print(f"Setup failure: {ex}")
                return make_request(DBManagerResponseTypes.error, 0)

        try:
            res = f(*args, **kwargs, cursor=cursor)
            conn.commit()
            res = 0 if res is None else res
        except Exception as ex:
            print(f"DBManager failure: {ex}")
            obj.is_set_up = False
            return make_request(DBManagerResponseTypes.error, 0)

        cursor.close()
        conn.close()
        return make_request(DBManagerResponseTypes.ok, res)
    return wrapper


class DBManager(ABC):
    is_set_up = False

    @with_cursor
    def set_up(self, cursor):
        pass

    @with_cursor
    def create_tables(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS user_online_activity_objects (tracked_user Bigint, game_id Bigint, started_playing_timestamp Bigint, ended_playing_timestamp Bigint, total_played float);")
        cursor.execute("CREATE TABLE IF NOT EXISTS telegram_bot_ignore_table (chat_id Bigint, steam_id Bigint);")

    @with_cursor
    def add_user_online_activity_object(self, data, cursor):
        cursor.execute(f"INSERT INTO user_online_activity_objects VALUES ({data['tracked_user']}, {data['game_id']}, {data['started_playing_timestamp']}, {data['ended_playing_timestamp']}, {data['total_played']});")

    @with_cursor
    def add_ignore_entry(self, data, cursor):
        cursor.execute(f"SELECT * FROM telegram_bot_ignore_table WHERE chat_id = {data['chat_id']} and steam_id = {data['steam_id']} LIMIT 1;")
        if cursor.fetchone() is None:
            cursor.execute(f"INSERT INTO telegram_bot_ignore_table VALUES ({data['chat_id']}, {data['steam_id']});")

    @with_cursor
    def get_ignore_steam_ids_by_chat_id(self, data, cursor):
        cursor.execute(f"SELECT steam_id FROM telegram_bot_ignore_table WHERE chat_id = {data['chat_id']};")
        return cursor.fetchall()

    @with_cursor
    def get_ignore_chat_ids_by_steam_id(self, data, cursor):
        cursor.execute(f"SELECT chat_id FROM telegram_bot_ignore_table WHERE steam_id = {data['steam_id']};")
        return cursor.fetchall()

    @with_cursor
    def remove_ignore_entry(self, data, cursor):
        cursor.execute(f"SELECT * FROM telegram_bot_ignore_table WHERE chat_id = {data['chat_id']} and steam_id = {data['steam_id']} LIMIT 1;")
        if cursor.fetchone() is not None:
            cursor.execute(f"DELETE FROM telegram_bot_ignore_table WHERE chat_id = {data['chat_id']} and steam_id = {data['steam_id']};")

    @with_cursor
    def get_user_online_activity_objects(self, data, cursor):
        true_request = "1=1"

        start_timestamp = data["start_timestamp"]
        start_timestamp_request = f"started_playing_timestamp >= {start_timestamp}" if start_timestamp else true_request

        end_timestamp = data["end_timestamp"]
        end_timestamp_request = f"ended_playing_timestamp <= {end_timestamp}" if end_timestamp else true_request

        tracked_users = data["tracked_users"]
        tracked_users_request = true_request
        if tracked_users == []:
            return []
        if tracked_users:
            tracked_users = [str(x) for x in tracked_users]
            tracked_users_str = "(" + ", ".join(tracked_users) + ")"
            tracked_users_request = f"tracked_user in {tracked_users_str}"

        game_ids = data["game_ids"]
        game_ids_request = true_request
        if game_ids == []:
            return []
        if game_ids:
            game_ids = [str(x) for x in game_ids]
            game_ids_str = "(" + ", ".join(game_ids) + ")"
            game_ids_request = f"game_id in {game_ids_str}"

        request = f"SELECT * FROM user_online_activity_objects WHERE \
            {start_timestamp_request} AND {end_timestamp_request} AND \
            {tracked_users_request} AND {game_ids_request};"
        cursor.execute(request)
        return cursor.fetchall()

    @with_cursor
    def get_users_with_data(self, data, cursor):
        request = f"SELECT DISTINCT tracked_user FROM user_online_activity_objects;"
        cursor.execute(request)
        return [element[0] for element in cursor.fetchall()]

    @with_cursor
    def get_games_with_data(self, data, cursor):
        request = f"SELECT DISTINCT game_id FROM user_online_activity_objects;"
        cursor.execute(request)
        return [element[0] for element in cursor.fetchall()]


class SqliteManager(DBManager):
    def __init__(self, db_name):
        self.db_name = db_name
        create_file_if_not_exists(self.db_name)

        self.db_module = sqlite3
        self.connection_dict = {
            "database": self.db_name,
            "isolation_level": None
        }

        self.set_up()

    @with_cursor
    def create_backup_csv(self, cursor):
        save_path = "" + f"{dt.datetime.utcnow().timestamp()}.csv"
        with open(save_path, 'w') as file:
            cursor.execute('SELECT * FROM user_online_activity_objects')
            csv_out = csv.writer(file)
            csv_out.writerow([d[0] for d in cursor.description])
            for result in cursor:
                csv_out.writerow(result)


class PostgreSQLManager(DBManager):
    def __init__(self, user, password, host, port, db_name):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.db_name = db_name

        self.db_module = psycopg2
        self.connection_dict = {
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": self.port,
            "dbname": self.db_name
        }

        self.set_up()

    @with_cursor
    def create_backup_csv(self, cursor):
        s = "SELECT * FROM user_online_activity_objects"
        query = f"COPY ({s}) TO STDOUT WITH CSV HEADER"
        save_path = "" + f"{dt.datetime.utcnow().timestamp()}.csv"

        with open(save_path, 'w') as file:
            cursor.copy_expert(query, file)
