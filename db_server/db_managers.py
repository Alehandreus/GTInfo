import os
import sqlite3
import psycopg2
import datetime as dt


def create_file_if_not_exists(filepath):
    if not os.path.isfile(filepath):
        with open(filepath, "w"):
            pass


def with_sqlite3_cursor(f):
    def wrapper(*args, **kwargs):
        obj = args[0]
        conn = sqlite3.connect(obj.db_name, isolation_level=None)
        cursor = conn.cursor()
        res = f(*args, **kwargs, cursor=cursor)
        cursor.close()
        conn.close()
        return res
    return wrapper


def with_postgre_cursor(f):
    def wrapper(*args, **kwargs):
        obj = args[0]
        conn = psycopg2.connect(user=obj.user, password=obj.password, host=obj.host, port=obj.port, dbname=obj.db_name)
        cursor = conn.cursor()
        res = f(*args, **kwargs, cursor=cursor)
        conn.commit()
        cursor.close()
        conn.close()
        return res
    return wrapper


class SqliteManager:
    def __init__(self, db_name):
        self.db_name = db_name
        create_file_if_not_exists(self.db_name)
        self.create_tables()

    @with_sqlite3_cursor
    def create_tables(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS `user_online_activity_objects` (tracked_user Bigint, game_id Bigint, started_playing_timestamp Bigint, ended_playing_timestamp Bigint, total_played float)")
        cursor.execute("CREATE TABLE IF NOT EXISTS `telegram_bot_ignore_list` (chat_id Bigint, steam_id Bigint)")

    @with_sqlite3_cursor
    def add_play_interval(self, data, cursor):
        cursor.execute(f"INSERT INTO `user_online_activity_objects` VALUES ({data['tracked_user']}, {data['game_id']}, {data['started_playing_timestamp']}, {data['ended_playing_timestamp']}, {data['total_played']})")

    @with_sqlite3_cursor
    def add_ignore_entry(self, data, cursor):
        cursor.execute(f"SELECT * FROM `telegram_bot_ignore_table` WHERE chat_id = {data['chat_id']} and steam_id = {data['steam_id']} LIMIT 1")
        if cursor.fetchone() is None:
            cursor.execute(f"INSERT INTO `telegram_bot_ignore_table` VALUES ({data['chat_id']}, {data['steam_id']})")

    @with_sqlite3_cursor
    def get_ignore_steam_ids_by_chat_id(self, data, cursor):
        cursor.execute(f"SELECT steam_id FROM `telegram_bot_ignore_table` WHERE chat_id = {data['chat_id']}")
        return cursor.fetchall()

    @with_sqlite3_cursor
    def get_ignore_chat_ids_by_steam_id(self, data, cursor):
        cursor.execute(f"SELECT chat_id FROM `telegram_bot_ignore_table` WHERE steam_id = {data['steam_id']}")
        return cursor.fetchall()

    @with_sqlite3_cursor
    def remove_ignore_entry(self, data, cursor):
        cursor.execute(f"SELECT * FROM `telegram_bot_ignore_table` WHERE chat_id = {data['chat_id']} and steam_id = {data['steam_id']} LIMIT 1")
        if cursor.fetchone() is not None:
            cursor.execute(f"DELETE FROM `telegram_bot_ignore_table` WHERE chat_id = {data['chat_id']} and steam_id = {data['steam_id']}")


class PostgreSQLManager:
    def __init__(self, user, password, host, port, db_name):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.db_name = db_name
        self.create_tables()

    @with_postgre_cursor
    def create_backup_csv(self, cursor):
        s = "SELECT * FROM user_online_activity_objects"
        query = f"COPY ({s}) TO STDOUT WITH CSV HEADER"
        save_path = "" + f"{dt.datetime.utcnow()}.csv"

        with open(save_path, 'w') as file:
            cursor.copy_expert(query, file)

    @with_postgre_cursor
    def create_tables(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS user_online_activity_objects (tracked_user Bigint, game_id Bigint, started_playing_timestamp Bigint, ended_playing_timestamp Bigint, total_played float);")
        cursor.execute("CREATE TABLE IF NOT EXISTS telegram_bot_ignore_table (chat_id Bigint, steam_id Bigint);")

    @with_postgre_cursor
    def add_play_interval(self, data, cursor):
        cursor.execute(f"INSERT INTO user_online_activity_objects VALUES ({data['tracked_user']}, {data['game_id']}, {data['started_playing_timestamp']}, {data['ended_playing_timestamp']}, {data['total_played']});")

    @with_postgre_cursor
    def add_ignore_entry(self, data, cursor):
        cursor.execute(f"SELECT * FROM telegram_bot_ignore_table WHERE chat_id = {data['chat_id']} and steam_id = {data['steam_id']} LIMIT 1;")
        if cursor.fetchone() is None:
            cursor.execute(f"INSERT INTO telegram_bot_ignore_table VALUES ({data['chat_id']}, {data['steam_id']});")

    @with_postgre_cursor
    def get_ignore_steam_ids_by_chat_id(self, data, cursor):
        cursor.execute(f"SELECT steam_id FROM telegram_bot_ignore_table WHERE chat_id = {data['chat_id']};")
        return cursor.fetchall()

    @with_postgre_cursor
    def get_ignore_chat_ids_by_steam_id(self, data, cursor):
        cursor.execute(f"SELECT chat_id FROM telegram_bot_ignore_table WHERE steam_id = {data['steam_id']};")
        return cursor.fetchall()

    @with_postgre_cursor
    def remove_ignore_entry(self, data, cursor):
        cursor.execute(f"SELECT * FROM telegram_bot_ignore_table WHERE chat_id = {data['chat_id']} and steam_id = {data['steam_id']} LIMIT 1;")
        if cursor.fetchone() is not None:
            cursor.execute(f"DELETE FROM telegram_bot_ignore_table WHERE chat_id = {data['chat_id']} and steam_id = {data['steam_id']};")
