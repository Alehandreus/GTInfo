import os
import sqlite3
import psycopg2


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

    @with_sqlite3_cursor
    def add_play_interval(self, data, cursor):
        cursor.execute(f"INSERT INTO `user_online_activity_objects` VALUES ({data['tracked_user']}, {data['game_id']}, {data['started_playing_timestamp']}, {data['ended_playing_timestamp']}, {data['total_played']})")


class PostgreSQLManager:
    def __init__(self, user, password, host, port, db_name):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.db_name = db_name
        self.create_tables()

    @with_postgre_cursor
    def create_tables(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS user_online_activity_objects (tracked_user Bigint, game_id Bigint, started_playing_timestamp Bigint, ended_playing_timestamp Bigint, total_played float);")

    @with_postgre_cursor
    def add_play_interval(self, data, cursor):
        cursor.execute(f"INSERT INTO user_online_activity_objects VALUES ({data['tracked_user']}, {data['game_id']}, {data['started_playing_timestamp']}, {data['ended_playing_timestamp']}, {data['total_played']});")
