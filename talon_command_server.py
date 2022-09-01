# This is a naive port of pokey's typescript Talon command server, which was
# originally written for VSCode https://github.com/pokey/command-server
#
# This is designed to be usable generically by any python extension that needs
# to act as a command server. See documentation for API usage.
#
# TODO:
# - How do we deal with multiple instances of the same app?


import pathlib
import stat
import os
import json
import datetime
import time
import threading
import queue


class TalonCommandServer:
    REQUEST_PATH = "request.json"
    RESPONSE_PATH = "response.json"
    STALE_TIMEOUT_MS = 60000
    COMMAND_TIMEOUT_MS = 3000

    def __init__(self, path):
        suffix = ""
        if hasattr(os, "getuid"):
            suffix = f"-{os.getuid()}"
        path = f"{path}{suffix}"
        self.communication_directory = pathlib.Path(path)
        self.request_file = self.communication_directory / self.REQUEST_PATH
        self.response_file = self.communication_directory / self.RESPONSE_PATH
        result = self.initialize_communication_dir()
        if not result:
            print("ERROR: Unable to initialize communication directory")
            self.init_ok = False
            return
        self.init_ok = True

    def read_request(self):
        """Reads the JSON-encoded request from the request file

        The request file will be unlinked after being read.

        A request is formatted as:
         command_id: string;
            - The id of the command to run
         uuid: string;
            - A uuid that will be written to the response file for sanity checking client-side
         args: list;
            - Arguments to the command, if any
         return_command_output: boolean;
            - A boolean indicating if we should return the output of the command
         wait_for_finish: boolean;
            - A boolean indicating if we should await the command to ensure it is complete.  This behaviour is desirable for some commands and not others. For most commands it is ok, and can remove race conditions, but for some commands, such as ones that show a quick picker, it can hang the client

        Returns parsed request or None
        """

        timestamp = self.request_file.stat().st_mtime
        current = datetime.datetime.now().timestamp()

        request = None
        if int(current - timestamp) * 1000 > self.COMMAND_TIMEOUT_MS:
            print("WARNING: Request is stale. Will delete.")
        else:
            if self.request_file.stat()[stat.ST_SIZE] == 0:
                return None
            with self.request_file.open("r") as request:
                try:
                    request = json.load(request)
                except json.decoder.JSONDecodeError:
                    return None

        self.request_file.unlink()
        return request

    def write_response(self, response):
        """Write JSON-encoded response to request file"""
        # XXX - Cursorless uses wx, which fails if the file exists...
        with open(self.response_file, "w+") as f:
            f.write(json.dumps(response) + '\n')

    def initialize_communication_dir(self):
        """Initialize the RPC directory"""
        path = self.communication_directory
        path.mkdir(mode=0o770, parents=True, exist_ok=True)

        # Basic sanity validation
        stats = path.stat()
        if (
            not path.is_dir()
            or path.is_symlink()
            or stats.st_mode & stat.S_IWOTH
            or (stats[stat.ST_UID] >= 0 and stats[stat.ST_UID] != os.getuid())
        ):
            print(
                f"ERROR: Unable to create communication directory: {self.communication_directory}"
            )
            return False
        return True

    def validate_request(self, request):
        """Ensure that all of the required fields are in the request"""
        required_fields = [
            "commandId",
            "args",
            "uuid",
            "returnCommandOutput",
            "waitForFinish",
        ]
        valid = True
        for field in required_fields:
            if field not in request.keys():
                print(f"ERROR: request is missing required field {field}")
                valid = False
                print(request)
        return valid

    def command_thread(self, data_queue, request, command_handler):
        """A new thread to invoke the command handler"""
        result = command_handler(request["commandId"], *request["args"])
        if data_queue:
            data_queue.put(result)
        return

    def run_command(self, request, handler, do_async):
        """Runs a command handler in a new thread

        Optionally waits for the response if async is false"""

        data_queue = None
        if not do_async:
            data_queue = queue.Queue()
        t = threading.Thread(
            target=self.command_thread, args=(data_queue, request, handler)
        )
        if do_async:
            t.daemon = True
            t.start()
            return None
        else:
            t.start()
            output = data_queue.get()
            t.join()
            return output

    def command_loop(self, command_handler):
        """Loop indefinitely waiting for new commands"""
        while True:
            if not self.request_file.exists():
                time.sleep(0.01)
                continue

            request = self.read_request()
            if not request:
                continue
            if not self.validate_request(request):
                print("WARNING: Received bad request. Ignoring")
                continue

            do_async = True
            if request["returnCommandOutput"] or request["waitForFinish"]:
                do_async = False
            output = self.run_command(request, command_handler, do_async)

            # XXX - Add proper error handling
            error = None
            warnings = None
            response = {}
            response["returnValue"] = output
            response["error"] = error
            response["uuid"] = request["uuid"]
            response["warnings"] = warnings
            self.write_response(response)
