"""Validated launcher for Froja Action Video.

Keeps the bridge implementation isolated while normalizing FFmpeg duration values
for Windows builds that require a leading zero.
"""
from http.server import ThreadingHTTPServer

import froja_action_video_bridge as bridge

_run = bridge.subprocess.run


def normalized_run(command, *args, **kwargs):
    fixed = []
    for value in command:
        if isinstance(value, str):
            value = value.replace("d=.75", "d=0.75").replace("d=.20", "d=0.20").replace("d=.45", "d=0.45")
        fixed.append(value)
    return _run(fixed, *args, **kwargs)


bridge.subprocess.run = normalized_run

if __name__ == "__main__":
    bridge.OUTPUT.mkdir(parents=True, exist_ok=True)
    print(f"Froja Action Video v2: http://127.0.0.1:{bridge.PORT}")
    ThreadingHTTPServer(("127.0.0.1", bridge.PORT), bridge.Handler).serve_forever()
