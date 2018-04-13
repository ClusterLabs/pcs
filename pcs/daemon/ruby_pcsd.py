import base64
import json
from collections import namedtuple
from os.path import dirname, realpath, abspath, join as join_path

from tornado.gen import Task, multi, convert_yielded
from tornado.httputil import split_host_and_port, HTTPServerRequest
from tornado.process import Subprocess


PCSD_DIR = realpath(dirname(abspath(__file__))+ "/../../pcsd")
PUBLIC_DIR = join_path(PCSD_DIR, "public")
PCSD_CMD = "sinatra_cmdline_wrapper.rb"

SINATRA_GUI = "sinatra_gui"
SINATRA_REMOTE = "sinatra_remote"
SYNC_CONFIGS = "sync_configs"


SinatraResult = namedtuple("SinatraResult", "headers, status, body")

def json_to_sinatra_result(result_json) -> SinatraResult:
    try:
        result = json.loads(result_json)
    except Exception as e:
        #TODO log?
        raise e

    return SinatraResult(
        result["headers"],
        result["status"],
        base64.b64decode(result["body"])
    )

class Wrapper:
    def __init__(self, gem_home, debug=False, ruby_executable="ruby"):
        self.__gem_home = gem_home
        self.__ruby_executable = ruby_executable
        self.__debug = debug

    def get_ruby_request(self, request_type):
        return {
            "type": request_type,
            "config": {
                # TODO in real server it is /var/lib/pcsd/
                "user_pass_dir": PCSD_DIR,
                "debug": self.__debug,
            },
        }

    def get_sinatra_request(self, request_type, request: HTTPServerRequest):
        sinatra_request = self.get_ruby_request(request_type)

        host, port = split_host_and_port(request.host)
        sinatra_request.update({
            "env": {
                "PATH_INFO": request.path,
                "QUERY_STRING": request.query,
                "REMOTE_ADDR": request.remote_ip,
                "REMOTE_HOST": request.host,
                "REQUEST_METHOD": request.method,
                "REQUEST_URI": f"{request.protocol}://{request.host}{request.uri}",
                "SCRIPT_NAME": "",
                "SERVER_NAME": host,
                "SERVER_PORT": port,
                "SERVER_PROTOCOL": request.version,
                "HTTP_HOST": request.host,
                "HTTP_ACCEPT": "*/*",
                "HTTP_COOKIE": ";".join([
                    v.OutputString() for v in request.cookies.values()
                ]),
                "HTTPS": "on" if request.protocol == "https" else "off",
                "HTTP_VERSION": request.version,
                "REQUEST_PATH": request.uri,
                "rack.input": request.body.decode("utf8"),
            }
        })
        return sinatra_request

    async def run_ruby(self, request: HTTPServerRequest):
        pcsd_ruby = Subprocess(
            [
                self.__ruby_executable, "-I",
                PCSD_DIR,
                join_path(PCSD_DIR, PCSD_CMD)
            ],
            stdin=Subprocess.STREAM,
            stdout=Subprocess.STREAM,
            stderr=Subprocess.STREAM,
            env={
                "GEM_HOME": self.__gem_home,
            }
        )

        await Task(pcsd_ruby.stdin.write, str.encode(json.dumps(request)))
        pcsd_ruby.stdin.close()
        result_json, dummy_error = await multi([
            Task(pcsd_ruby.stdout.read_until_close),
            Task(pcsd_ruby.stderr.read_until_close),
        ])
        return result_json

    async def request_gui(
        self, request: HTTPServerRequest, user, groups, is_authenticated
    ) -> SinatraResult:
        sinatra_request = self.get_sinatra_request(SINATRA_GUI, request)
        # Session was taken from ruby. However, some session information is needed
        # for ruby code (e.g. rendering some parts of templates). So this
        # information must be sent to ruby by another way.
        sinatra_request.update({
            "session": {
                "username": user,
                "groups": groups,
                "is_authenticated": is_authenticated,
            },
        })
        result_json = await convert_yielded(self.run_ruby(sinatra_request))
        return json_to_sinatra_result(result_json)

    async def request_remote(self, request: HTTPServerRequest) -> SinatraResult:
        sinatra_request = self.get_sinatra_request(SINATRA_REMOTE, request)
        result_json = await convert_yielded(self.run_ruby(sinatra_request))
        return json_to_sinatra_result(result_json)

    async def sync_configs(self):
        result_json = await convert_yielded(
            self.run_ruby(self.get_ruby_request(SYNC_CONFIGS))
        )
        return json.loads(result_json)["next"]
