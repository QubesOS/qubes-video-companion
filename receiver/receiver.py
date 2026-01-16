#!/usr/bin/python3 --

# Copyright (C) 2021 Elliot Killick <elliotkillick@zohomail.eu>
# Copyright (C) 2021 Demi Marie Obenour <demi@invisiblethingslab.com>
# Licensed under the MIT License. See LICENSE file for details.

import sys
import socket
import struct
import os
from typing import NoReturn


def sdnotify(msg):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    addr = os.getenv("NOTIFY_SOCKET")
    if addr[0] == "@":
        addr = '\0' + addr[1:]
    sock.connect(addr)
    sock.sendall(msg)
    sock.close()

def main(argv) -> NoReturn:
    dev_path = "/dev/video0"
    if len(argv) == 2:
        dev_path = argv[1]
    elif len(argv) != 1:
        raise RuntimeError(
            "wrong arguments - expected only optional device path"
        )

    width, height, fps = read_video_parameters()

    if "NOTIFY_SOCKET" in os.environ:
        sdnotify(b"READY=1")
    print(
        "Receiving video stream at {}x{} {} FPS...".format(width, height, fps),
        file=sys.stderr,
    )
    os.execv(
        "/usr/bin/gst-launch-1.0",
        (
            "gst-launch-1.0",
            "fdsrc",
            "!",
            "queue",
            "!",
            "capsfilter",
            "caps=video/x-raw,"
            "width={0},"
            "height={1},"
            "framerate={2}/1,"
            "format=I420,"
            "colorimetry=2:4:7:1,"
            "chroma-site=none,"
            "interlace-mode=progressive,"
            "pixel-aspect-ratio=1/1,"
            "max-framerate={2}/1,"
            "views=1".format(width, height, fps),
            "!",
            "rawvideoparse",
            "use-sink-caps=true",
            "!",
            "v4l2sink",
            "device=" + dev_path,
            "sync=false",
        ),
    )


def read_video_parameters() -> (int, int, int):
    input_size = 6

    sstruct = struct.Struct("=HHH")
    if sstruct.size != input_size:
        raise AssertionError("bug")

    untrusted_input = os.read(0, input_size)

    if len(untrusted_input) == 0:
        print("Operation canceled by sender", file=sys.stderr)
        sys.exit(1)

    if len(untrusted_input) != input_size:
        raise RuntimeError("wrong number of bytes read")
    untrusted_width, untrusted_height, untrusted_fps = sstruct.unpack(
        untrusted_input
    )
    del untrusted_input

    if (
        untrusted_width > 7680
        or untrusted_height > 4320
        or untrusted_fps > 4096
    ):
        raise RuntimeError("excessive width, height, and/or fps (max 8K: 7680x4320)")
    width, height, fps = untrusted_width, untrusted_height, untrusted_fps
    del untrusted_width, untrusted_height, untrusted_fps

    return width, height, fps


if __name__ == "__main__":
    main(sys.argv)
