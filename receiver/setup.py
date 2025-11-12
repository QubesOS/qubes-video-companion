#!/usr/bin/python3 --
#
# Copyright (C) 2025 Marek Marczykowski-Górecki
#                            <marmarek@invisiblethingslab.com>
# Licensed under the MIT License. See LICENSE file for details.


import sys
import struct
import os
import fcntl
import subprocess

# see v4l2loopback.h:
#    __s32 output_nr;
#    __s32 unused; /*capture_nr;*/
#
#    /**
#         * a nice name for your device
#         * if (*card_label)==0, an automatic name is assigned
#         */
#    char card_label[32];
#
#    /**
#         * allowed frame size
#         * if too low, default values are used
#         */
#    __u32 min_width;
#    __u32 max_width;
#    __u32 min_height;
#    __u32 max_height;
#
#    /**
#         * number of buffers to allocate for the queue
#         * if set to <=0, default values are used
#         */
#    __s32 max_buffers;
#
#    /**
#         * how many consumers are allowed to open this device concurrently
#         * if set to <=0, default values are used
#         */
#    __s32 max_openers;
#
#    /**
#         * set the debugging level for this device
#         */
#    __s32 debug;
#
#    /**
#         * whether to announce OUTPUT/CAPTURE capabilities exclusively
#         * for this device or not
#         * (!exclusive_caps)
#     * NOTE: this is going to be removed once separate output/capture
#     *       devices are implemented
#         */
#    __s32 announce_all_caps;
v4l2_loopback_config_format = "ii32sIIIIiiii"


# V4L2LOOPBACK_CTL_ADD = 0x40487e01
# use legacy numbers since the change was recent
V4L2LOOPBACK_CTL_ADD = 0x4C80


def register_device(name):
    ctrl_fd = os.open("/dev/v4l2loopback", os.O_RDWR)
    try:
        if not name:
            name = "Qubes Video Companion"
        # arg is v4l2_loopback_config config struct
        conf = bytearray(
            struct.pack(
                v4l2_loopback_config_format,
                -1,  # output_nr (auto)
                -1,  # unused
                name.encode(),  # card_label
                0,  # min_width
                0,  # max_width
                0,  # min_height
                0,  # max_height
                0,  # max_buffers
                0,  # max_openers
                0,  # debug
                0,  # announce_all_caps
            )
        )
        ret = fcntl.ioctl(ctrl_fd, V4L2LOOPBACK_CTL_ADD, conf)
        return ret
    finally:
        os.close(ctrl_fd)


def main(argv):
    name = None
    if len(argv) == 2:
        name = f"QVC - {argv[1]}"
    elif len(argv) != 1:
        raise RuntimeError("Invalid arguments - usage: setup.py [name]")
    if not os.path.exists("/dev/v4l2loopback"):
        subprocess.check_call(
            ["sudo", "--non-interactive", "modprobe", "v4l2loopback"]
        )
    dev_nr = register_device(name)
    print(f"/dev/video{dev_nr}")


if __name__ == "__main__":
    main(sys.argv)
