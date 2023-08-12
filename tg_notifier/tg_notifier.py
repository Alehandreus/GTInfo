import datetime as dt
import json
from dataclasses import dataclass
from name_finder import NameFinder
from datetime import datetime
import asyncio
import aiogram
from asyncio_requests.asyncio_request import request
import signal
import socket
from gtinfo_requests import *
from binary_functions import *


# add 3 hours to date lol
def f(x):
    return dt.datetime.strftime(dt.datetime.fromtimestamp(x) + dt.timedelta(hours=3), format="%H:%M")


class GTInfoUser:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.notified_users = set()

    def __repr__(self):
        return f"GTInfo user with {self.chat_id}"

    def __eq__(self, other):
        return self.chat_id == other.chat_id and self.notified_users == other.notified_users

    def __hash__(self):
        return self.chat_id


class TGNotifier:
    @dataclass
    class Settings:
        users_retrieval_freq: int = 1

    @dataclass
    class Tasks:
        console_task: asyncio.Task = None
        socket_task: asyncio.Task = None
        update_task: asyncio.Task = None
        polling_task: asyncio.Task = None

    def __init__(self, bind_address, db_server_address, website_url, token):
        self.bot = aiogram.Bot(token=token)
        self.dp = aiogram.Dispatcher(self.bot)

        self.name_finder = NameFinder()

        self.BIND_ADDRESS = bind_address
        self.WEBSITE_URL = website_url
        self.db_server_address = db_server_address
        self.website_operational = True
        self.db_operational = True

        self.gtinfo_users = set()

        self.settings = self.Settings()
        self.tasks = self.Tasks()

    async def start(self):
        print("Telegram notifier starting...")
        signal.signal(signal.SIGTERM, self.stop)

        self.tasks.socket_task = asyncio.create_task(self.start_socket())
        self.tasks.update_task = asyncio.create_task(self.start_update())
        self.tasks.polling_task = asyncio.create_task(self.start_polling())

        tasks_list = [self.tasks.socket_task, self.tasks.update_task, self.tasks.polling_task]
        await asyncio.wait(tasks_list, return_when=asyncio.FIRST_COMPLETED)

        # tasks_list = [self.tasks.socket_task, self.tasks.update_task]
        # await asyncio.wait(tasks_list, return_when=asyncio.FIRST_COMPLETED)
        self.stop()

    def stop(self, *args):
        print("cancelling tasks")
        tasks_list = [self.tasks.socket_task, self.tasks.update_task, self.tasks.polling_task]
        for task in tasks_list:
            task.cancel()

    async def start_socket(self):
        print('Socket active')
        server = await asyncio.start_server(self.handle_connection, '0.0.0.0', 8000)
        async with server:
            await server.serve_forever()

    async def handle_connection(self, reader, writer):
        try:
            message = (await reader.read())[4:].decode()
            message = json.loads(message)
            if message["command"] == "new_user_online_activity_objects":
                await self.notify(message["user_online_activity_objects"])
        except Exception as ex:
            print("Error at handling connection: ", ex)
        writer.close()

    async def notify(self, user_online_activity_objects):
        print("received", user_online_activity_objects)
        for user_online_activity_object in user_online_activity_objects:
            for gtinfo_user in self.gtinfo_users:
                new_user = int(user_online_activity_object["tracked_user"])
                if new_user not in gtinfo_user.notified_users:
                    continue

                data = user_online_activity_object
                s = f"" \
                    f"{self.name_finder.get_username(data['tracked_user'])} was playing " \
                    f"{self.name_finder.get_appname(data['game_id'])} " \
                    f"({f(data['started_playing_timestamp'])} — {f(data['ended_playing_timestamp'])})"

                print("notifying user", gtinfo_user.chat_id)
                await self.bot.send_message(gtinfo_user.chat_id, s)

    async def start_update(self):
        print("Data collection active")
        while True:
            try:
                await self.retrieve_users()
                if not self.website_operational:
                    print(f"Website is operational since {dt.datetime.utcnow()} utc")
                self.website_operational = True
            except Exception as ex:
                if self.website_operational:
                    print(f"Website is not operational since {dt.datetime.utcnow()} utc")
                    print(ex)
                    self.website_operational = False
            await asyncio.sleep(self.settings.users_retrieval_freq)

    async def retrieve_users(self):
        new_gtinfo_users = set()

        resp = await request(f"{self.WEBSITE_URL}/notified_users", protocol="HTTPS", protocol_info={"request_type": "GET"})
        resp = json.loads(resp["api_response"]["content"])

        for el in resp["users"]:
            new_gtinfo_user = GTInfoUser(int(el["chat_id"]))
            new_gtinfo_user.notified_users = [int(a) for a in el["notified_users"]]
            new_gtinfo_users.add(new_gtinfo_user)

        if self.gtinfo_users != new_gtinfo_users:
            print(f"Users from {self.WEBSITE_URL}: {new_gtinfo_users}")

        self.gtinfo_users = new_gtinfo_users

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

    async def start_polling(self):
        @self.dp.message_handler(commands=['users_week', 'games_week', 'users_total', 'games_total'])
        async def echo_message(msg):
            # if msg.from_user.id != 750750506:
            #     print("not the one")
            #     return

            gtinfo_user = None
            for user in self.gtinfo_users:
                if user.chat_id == msg.from_user.id:
                    gtinfo_user = user

            comment = ""
            # "end_timestamp": int(datetime.now().timestamp())
            request_data = {"limit": 10, "tracked_users": list(gtinfo_user.notified_users)}
            request = None
            if msg.text == '/users_week':
                request = GTInfoRequestTypes.most_played_users
                request_data["start_timestamp"] = int(datetime.now().timestamp()) - 7 * 24 * 60 * 60
                comment = "Активные пользователи за последнюю неделю:\n"
            elif msg.text == '/users_total':
                request = GTInfoRequestTypes.most_played_users
                comment = "Активные пользователи за все время сервиса:\n"
            elif msg.text == '/games_week':
                request = GTInfoRequestTypes.most_played_games
                request_data["start_timestamp"] = int(datetime.now().timestamp()) - 7 * 24 * 60 * 60
                comment = "Популярные игры за последнюю неделю:\n"
            elif msg.text == '/games_total':
                request = GTInfoRequestTypes.most_played_games
                comment = "Популярные игры за все время сервиса:\n"

            print(msg.from_user.id, msg.text)
            # print(request, request_data)

            response_code, response_data = self.quick_request(request, request_data)
            if response_code != GTInfoResponseTypes.ok:
                await self.bot.send_message(msg.from_user.id, "Ошибка")
            # print(response_data)

            reply = comment
            if msg.text == '/users_week' or msg.text == '/users_total':
                for user in response_data:
                    reply += f"{self.name_finder.get_username(user[0])}: {user[1] // 3600}h\n"
            else:
                for game in response_data:
                    reply += f"{self.name_finder.get_appname(game[0])}: {game[1] // 3600}h\n"
            # print(reply)

            await self.bot.send_message(msg.from_user.id, reply)


        print("Pollin4g...")
        # self.dp.register_message_handler(3)
        await self.dp.start_polling(self.dp)
