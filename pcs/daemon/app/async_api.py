import json
import re
import tornado

from tornado.web import RequestHandler
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from ..scheduler.commands import Command

class TaskHandler(RequestHandler):
    def initialize(self, scheduler):
        self.scheduler = scheduler

    def prepare(self):
        self.add_header('Content-Type', 'application/x-json')
        if 'Content-Type' in self.request.headers \
                and \
                self.request.headers['Content-Type'] == 'application/x-json':
            try:
                self.json: Dict[str, Any] = json.loads(self.request.body)
            except json.JSONDecodeError:
                self.write_error(
                    400,
                    http_error="Bad Request",
                    error_msg="Malformed JSON data"
                )

    # Create new task
    def post(self):
        if not self.json:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task assignment is missing"
            )
        expected_keys: List[str] = ['command', 'params']
        if len(self.json) != 2 or \
                list(self.json.keys()).sort() != expected_keys.sort():
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Malformed task assignment"
            )

        task_ident = self.scheduler.new_task(
            Command(self.json['command'], self.json['params'])
        )

        self.write(
            json.dumps(dict(
                task_ident=task_ident
            ))
        )

    # Get task status
    def get(self):
        try:
            task_ident = self.get_query_argument("task_ident")
        except tornado.web.MissingArgumentError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Non-optional argument task_ident is missing"
            )
            return None
        self.validate_task_ident(task_ident)
        self.write(json.dumps(self.scheduler.get_task(task_ident)))


    # Kill task
    def delete(self):
        try:
            task_ident = self.get_query_argument("task_ident")
        except tornado.web.MissingArgumentError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Non-optional argument task_ident is missing"
            )
            return None
        self.validate_task_ident(task_ident)
        self.scheduler.kill_task(task_ident)


    def validate_task_ident(self, task_ident: str):
        try:
            if not re.fullmatch(r'[a-fA-F0-9]{32}', task_ident):
                self.write_error(
                    400,
                    http_error="Bad Request",
                    error_msg="Malformed task_ident"
                    )
        except re.error:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Malformed task_ident"
                )

    def write_error(self, status_code: int, http_error: str = None,
                    error_msg: str = None, hints: str = None, **kwargs):
        self.set_status(status_code, http_error)
        response: Dict[str, str] = {}
        if status_code:
            response['http_code'] = status_code
        if http_error:
            response['http_error'] = http_error
        if error_msg:
            response['error_message'] = error_msg
        if hints:
            response['hints'] = hints
        self.write(json.dumps(response))
        self.finish()

def get_routes(scheduler):
    return [
        ("/async_api/task", TaskHandler, dict(scheduler=scheduler)),
    ]
