#!/usr/bin/python3 --

# Copyright (C) 2021 Elliot Killick <elliotkillick@zohomail.eu>
# Copyright (C) 2021 Demi Marie Obenour <demi@invisiblethingslab.com>
# Licensed under the MIT License. See LICENSE file for details.

"""Webcam video source module"""

import sys
import re
import subprocess
from service import Service


class Webcam(Service):
    """Webcam video source class"""

    untrusted_requested_width: int
    untrusted_requested_height: int
    untrusted_requested_fps: int

    def __init__(self, *, untrusted_arg: str):
        if untrusted_arg:
            def parse_int(untrusted_decimal: bytes) -> int:
                if not ((1 <= len(untrusted_decimal) <= 4) and
                        untrusted_decimal.isdigit() and
                        untrusted_decimal[0] != "0"):
                    print("Invalid argument " + untrusted_arg + ": bad number",
                          file=sys.stderr)
                    sys.exit(1)
                return int(untrusted_decimal, 10)
            if len(untrusted_arg) > 14:
                # qrexec has already sanitized the argument to some degree,
                # so this is safe
                print("Invalid argument " + untrusted_arg +
                      ": too long (limit 14 bytes)", file=sys.stderr)
                sys.exit(1)
            arg_list = untrusted_arg.split("+", 4)
            if len(arg_list) != 3:
                print("Invalid argument " + untrusted_arg +
                      ": wrong number of integers (expected 3)",
                      file=sys.stderr)
                sys.exit(1)
            ( self.untrusted_requested_width
            , self.untrusted_requested_height
            , self.untrusted_requested_fps
            ) = map(parse_int, arg_list)
        else:
            self.untrusted_requested_width = 0
            self.untrusted_requested_height = 0
            self.untrusted_requested_fps = 0

        Service.main(self)

    def video_source(self) -> str:
        return "webcam"

    def icon(self) -> str:
        return "camera-web"

    def parameters(self):
        mjpeg_re = re.compile(
            rb"\t\[[0-9]+]: 'MJPG' \(Motion-JPEG, compressed\)\Z"
        )
        fmt_re = re.compile(rb"\t\[[0-9]+]: ")
        dimensions_re = re.compile(rb"\t\tSize: Discrete [0-9]+x[0-9]+\Z")
        interval_re = re.compile(
            rb"\t\t\tInterval: Discrete [0-9.]+s \([0-9]+\.0+ fps\)\Z"
        )
        frac_interval_re = re.compile(
            rb"\t\t\tInterval: Discrete [0-9.]+s \([0-9]+\.0*[1-9][0-9]* "\
            rb"fps\)\Z"
        )
        proc = subprocess.run(
            ("v4l2-ctl", "--list-formats-ext"),
            stdout=subprocess.PIPE,
            check=True,
            env={"PATH": "/bin:/usr/bin", "LC_ALL": "C"},
        )
        formats = []
        for i in proc.stdout.split(b"\n"):
            if mjpeg_re.match(i):
                fmt = "image/jpeg"
            elif fmt_re.match(i):
                # try raw, if it doesn't match, gstreamer will tell you
                fmt = "video/x-raw"
            elif dimensions_re.match(i):
                width, height = map(int, i[17:].split(b"x"))
            elif interval_re.match(i):
                fps = int(i[22:].split(b"(", 1)[1].split(b".", 1)[0])
                formats.append((width, height, fps, {"fmt": fmt}))
            elif frac_interval_re.match(i):
                # factional FPS not supported
                continue
            elif i in (
                b"",
                b"ioctl: VIDIOC_ENUM_FMT",
                b"\tType: Video Capture",
            ):
                continue
            else:
                print("Cannot parse output %r of v4l2ctl" % i, file=sys.stderr)
        formats.sort(key=lambda x: x[0] * x[1] * x[2], reverse=True)
        if self.untrusted_requested_fps:
            formats.sort(key=lambda x:
                         (x[0] - self.untrusted_requested_width) ** 2 +
                         (x[1] - self.untrusted_requested_height) ** 2 +
                         (x[2] - self.untrusted_requested_fps) ** 2)
        return formats[0]

    def pipeline(self, width: int, height: int, fps: int, **kwargs):
        fmt = kwargs.get("fmt", "image/jpeg")
        caps = (
            "width={0},"
            "height={1},"
            "framerate={2}/1,"
            "interlace-mode=progressive,"
            "pixel-aspect-ratio=1/1,"
            "max-framerate={2}/1,"
            "views=1".format(width, height, fps)
        )
        if "jpeg" in fmt:
            convert = (
                "!",
                "capsfilter",
                "caps={},chroma-site=none,".format(fmt)
                + caps,
                "!",
                "jpegdec",
            )
        else:
            convert = (
                    "!",
                    "videoconvert",
                    # workaround until
                    # https://gitlab.freedesktop.org/gstreamer/gstreamer/-/merge_requests/3713
                    # get merged:
                    # no-op filter that copies the frame based on its actual
                    # size, to discard padding
                    "!",
                    "videoflip",
                    )
        return [
            "v4l2src",
            "!",
            "queue",
            *convert,
            "!",
            "capsfilter",
            "caps=video/x-raw,format=I420," + caps,
            "!",
            "fdsink",
        ]


if __name__ == "__main__":
    _untrusted_arg = ""
    if len(sys.argv) == 2:
        _untrusted_arg = sys.argv[1]
    elif len(sys.argv) != 1:
        print("Must have 0 or 1 argument, not " + str(len(sys.argv)),
              file=sys.stderr)
        sys.exit(1)
    webcam = Webcam(untrusted_arg=_untrusted_arg)
