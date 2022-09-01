This is a python implementation of the file-based RPC command server for use
with [Talon](https://talonvoice.com/) clients. This is mostly just a port of
the original Typescript implementation by Pokey
[here](https://github.com/pokey/command-server). 

The implementation is fairly generic, the ideas that any application plugin
written in python could import this class, and relatively seamlessly talk with
a command client on the talon side. The command client on the talon side is
currently a working process
[here](https://github.com/knausj85/knausj_talon/pull/956), but this server has
been tested with it to make sure it works fine.

# Usage

A simple example of how a python plugin can use the server:

```python
from .talon_command_server import TalonCommandServer

class ExampleCommandServer:
    COMMUNICATION_DIRECTORY = "/tmp/example-talon"

    def __init__(self, command_handler):
        self.command_handler = command_handler

    def start_server(self):
        server = TalonCommandServer(self.COMMUNICATION_DIRECTORY)
        if not server.init_ok:
            print("ERROR: Unable to initialize command server. Exiting early.")
            return
        server.command_loop(self.command_handler)

def command_handler(command, *args):
    """Main handler of all commands coming from Talon"""
    print(f"example command handler: {command} {args}")
    return "example command response"

# Plugin entry point
def main():
    server = command_server.ExampleCommandServer(command_handler)
    t = threading.Thread(target=server.start_server)
    t.daemon = True
    t.start()

if __name__ == "__main__":
    main()
```

# Installation

At the moment talon_command_server.py is just meant to be copied to the plugin
source directory that you're developing from, but in the future maybe we can
standardize on something like $HOME/.talon/lib/python/ for installing helper
stuff like this.
