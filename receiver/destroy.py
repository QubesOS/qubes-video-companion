#!/usr/bin/python3 --
#
# Copyright (C) 2025 Marek Marczykowski-Górecki
#                            <marmarek@invisiblethingslab.com>
# Licensed under the MIT License. See LICENSE file for details.

import errno
import sys
import os
import fcntl
import time
import subprocess


# V4L2LOOPBACK_CTL_REMOVE = 0x40487e02
# use legacy numbers since the change was recent
V4L2LOOPBACK_CTL_REMOVE = 0x4C81


def unregister_device(dev_nr):
    ctrl_fd = os.open("/dev/v4l2loopback", os.O_RDWR)
    try:
        message = ("Please close any window that has an open video stream "
            "so kernel modules can be securely unloaded...")

        while True:
            try:
                fcntl.ioctl(ctrl_fd, V4L2LOOPBACK_CTL_REMOVE, dev_nr)
                break
            except OSError as e:
                if e.errno == errno.EBUSY:
                    print(message, file=sys.stderr)
                    subprocess.call(
                        ["notify-send", "Qubes Video Companion", message]
                    )
                    time.sleep(10)
                else:
                    raise
    finally:
        os.close(ctrl_fd)


def main(argv):
    if len(argv) != 2 or not argv[1].startswith("/dev/video"):
        raise RuntimeError("Wrong arguments, expected /dev/video* path")
    dev_nr = int(argv[1][len("/dev/video") :])
    unregister_device(dev_nr)


if __name__ == "__main__":
    main(sys.argv)
