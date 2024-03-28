import time
import logging
from enum import Enum
from queue import Queue

import requests

from exceptions import MessageException


class data:
    class api:
        auth = 'https://id.skyeng.ru/frame/login-submit'
        save = 'https://api-edu.skysmart.ru/api/v1/user/progress/save'
        join = 'https://api-edu.skysmart.ru/api/v1/lesson/join'
        config = 'https://api-edu.skysmart.ru/api/v1/user/config'
        preview = 'https://api-edu.skysmart.ru/api/v1/task/preview'
        finish = 'https://api-edu.skysmart.ru/api/v1/task/complete-for-student'
        start = 'https://api-edu.skysmart.ru/api/v1/task/start'
        jwt = 'https://id.skyeng.ru/user-api/v1/auth/jwt'

        @staticmethod
        def auth_body(login: str, password: str, csrf_token: str):
            return {'username': login, 'password': password, "csrfToken": csrf_token}

        @staticmethod
        def save_body(progress_id: str, user_id: int, score: int, room_hash: str):
            return {
                "progressType": "step",
                "progressId": progress_id,
                "userId": user_id,
                "score": score,
                "completeness": 100,
                "roomHash": room_hash,
                "skippedAt": None
            }

        @staticmethod
        def start_body(task: str):
            return {
                "taskHash": task,
                "userAgent": {
                    "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "browser": {
                        "name": "Chrome",
                        "version": "120.0.0.0",
                        "major": "120"},
                    "engine": {"name": "Blink",
                               "version": "120.0.0.0"},
                    "os": {"name": "Linux",
                           "version": "x86_64"},
                    "device": {},
                    "cpu": {"architecture": "amd64"}},
                "isRegistration": False
            }


class StateEnum(Enum):
    INIT = 0
    AUTH = 1
    START = 2
    SETUP = 3
    DO = 4
    FINISH = 5


class SkysmartMaker:
    def __init__(self, task: str, score: int = 100):

        self.task = task
        self.score = score

        self.session = requests.Session()

        self._token_global = None

        self._preview = {}

        self._room_hash: str | None = None

    def do(self, login, password):
        yield {"state": StateEnum.AUTH}
        self.auth(login, password)
        yield {"state": StateEnum.START}
        self.check_task()
        self.start()
        yield {"state": StateEnum.SETUP}
        for i in self.do_tasks():
            yield {"state": StateEnum.DO, "data": i}
        yield {"state": StateEnum.FINISH}

    def check_task(self):
        """Check if that task is exist"""

        response = self.session.post(data.api.preview, json={'taskHash': self.task})
        if response.status_code == 500:
            raise MessageException("Задание не найдено!")
        self._preview = response.json()

    def auth(self, login: str, password: str):
        """Authenticate by login and password, token is saved in session cookies"""

        resp = self.session.post(data.api.auth, data=data.api.auth_body(
            login, password,
            self._get_csrf_token())
        )
        if not resp.json().get('success', False):
            raise MessageException("Неправильный логин или пароль")
        self.session.post(data.api.jwt)  # acquire jwt token cookies
        token_global = self.session.cookies.get('token_global')
        session_global = self.session.cookies.get('session_global')
        self.session.cookies.set('token_global', token_global, domain='.skysmart.ru')
        self.session.cookies.set('session_global', session_global, domain='.skysmart.ru')

    def start(self):
        for i in range(5):
            try:
                json = self.session.post(data.api.start, json=data.api.start_body(self.task)).json()
                self._room_hash = json['roomHash']
            except Exception:
                continue
            else:
                break

    def _get_csrf_token(self):
        # I think that BeautifulSoup is overkill

        from bs4 import BeautifulSoup

        page = self.session.get("https://id.skyeng.ru/login?skin=skysmart")
        bs = BeautifulSoup(page.text, "html.parser")
        return bs.find('input', attrs={'name': 'csrfToken'}).get('value')

    def _get_user_id(self):
        for i in range(5):
            try:
                json = self.session.get(data.api.config).json()
                return json['userId']
            except Exception:
                continue

    def _get_subtasks(self) -> list[str]:
        try:
            return self._preview['meta']['stepUuids']
        except KeyError as e:
            logging.error(self._preview)
            raise e

    def do_tasks(self):
        user_id = self._get_user_id()
        subtasks = self._get_subtasks()
        subtasks_len = len(subtasks)

        for index, subtask in enumerate(subtasks):
            body = data.api.save_body(subtask, user_id, self.score, self._room_hash)
            self.session.post(data.api.save, json=body)
            yield index+1, subtasks_len

        self.session.post(data.api.finish, json={'roomHash': self._room_hash})
