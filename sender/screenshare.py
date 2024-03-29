#!/usr/bin/python3 --

# Copyright (C) 2021 Elliot Killick <elliotkillick@zohomail.eu>
# Copyright (C) 2021 Demi Marie Obenour <demi@invisiblethingslab.com>
# Licensed under the MIT License. See LICENSE file for details.

"""Screen sharing video source module"""

# GI requires version declaration before importing
# pylint: disable=wrong-import-position

import gi

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk
from service import Service
from typing import List, Tuple


class ScreenShare(Service):
    """Screen sharing video souce class"""

    def __init__(self) -> None:
        self.main(self)

    def video_source(self) -> str:
        return "screenshare"

    def icon(self) -> str:
        return "video-display"

    def parameters(self) -> Tuple[int, int, int]:
        monitor = Gdk.Display().get_default().get_monitor(0).get_geometry()
        screen = Gdk.Screen().get_default()
        kwargs = {
            "crop_t": monitor.y,
            "crop_l": monitor.x,
            "crop_r": screen.width() - monitor.x - monitor.width,
            "crop_b": screen.height() - monitor.y - monitor.height,
        }
        return (monitor.width, monitor.height, 30, kwargs)

    def pipeline(self, width: int, height: int, fps: int,
                 **kwargs) -> List[str]:
        caps = (
            "colorimetry=2:4:7:1,"
            "chroma-site=none,"
            "width={0},"
            "height={1},"
            "framerate={2}/1,"
            "interlace-mode=progressive,"
            "pixel-aspect-ratio=1/1,"
            "max-framerate={2}/1,"
            "views=1".format(width, height, fps)
        )
        return [
            "ximagesrc",
            "use-damage=false",
            "!",
            "queue",
            "!",
            "videocrop",
            "top=" + str(kwargs["crop_t"]),
            "left=" + str(kwargs["crop_l"]),
            "right=" + str(kwargs["crop_r"]),
            "bottom=" + str(kwargs["crop_b"]),
            "!",
            "capsfilter",
            "caps=video/x-raw,format=BGRx," + caps,
            "!",
            "videoconvert",
            "!",
            "capsfilter",
            "caps=video/x-raw,format=I420," + caps,
            "!",
            "fdsink",
        ]


if __name__ == "__main__":
    screenshare = ScreenShare()
