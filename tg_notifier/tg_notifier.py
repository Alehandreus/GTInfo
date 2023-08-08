import datetime as dt
import json
from dataclasses import dataclass
from name_finder import NameFinder
import asyncio
import aiogram
from asyncio_requests.asyncio_request import request
import signal


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

    def __init__(self, bind_address, website_url, token):
        self.bot = aiogram.Bot(token=token)
        self.dp = aiogram.Dispatcher(self.bot)

        self.name_finder = NameFinder()

        self.BIND_ADDRESS = bind_address
        self.WEBSITE_URL = website_url

        self.website_operational = True

        self.gtinfo_users = set()

        self.settings = self.Settings()
        self.tasks = self.Tasks()

    async def start(self):
        print("Telegram notifier starting...")
        signal.signal(signal.SIGTERM, self.stop)

        self.tasks.socket_task = asyncio.create_task(self.start_socket())
        self.tasks.update_task = asyncio.create_task(self.start_update())

        tasks_list = [self.tasks.socket_task, self.tasks.update_task]
        await asyncio.wait(tasks_list)

        # tasks_list = [self.tasks.socket_task, self.tasks.update_task]
        # await asyncio.wait(tasks_list, return_when=asyncio.FIRST_COMPLETED)
        # self.stop()

    def stop(self, *args):
        print("cancelling tasks")
        tasks_list = [self.tasks.socket_task, self.tasks.update_task]
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
