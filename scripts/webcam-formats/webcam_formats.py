#!/usr/bin/python3

# Copyright (C) 2021 Elliot Killick <elliotkillick@zohomail.eu>
# Licensed under the MIT License. See LICENSE file for details.

"""Get and compare supported webcam formats"""

import argparse
import subprocess
from collections import OrderedDict
import qubesdb


class WebcamFormats:
    """
    Parse supported webcam formats

    Output from: v4l2-ctl --device /dev/videoX --list-formats-ext
    """

    formats = ""
    formats_len = 0
    video_device = ""

    __line_idx = 0

    pix_fmt = {}

    selected_format = ""
    selected_size = ()
    selected_fps = 0

    def __init__(self, formats, video_device="/dev/video0"):
        self.formats = formats
        self.formats_len = len(self.formats)

        self.video_device = video_device

        while self.__line_idx < self.formats_len:
            line = self.formats[self.__line_idx]

            if line.startswith("["):
                self.__index()

            self.__line_idx = self.__line_idx + 1

    def __index(self):
        """Parse each pixel format by index value"""

        # We must use a while loop because Python's for loop doesn't
        # allow changing the index while inside the loop
        # Python's for loop is like other languages foreach loop
        while self.__line_idx < self.formats_len:
            line = self.formats[self.__line_idx]

            if line.startswith("["):
                # Remove removing surrounding single quotes (') junk
                pix_fmt = line.split()[1].replace("'", "")
                self.pix_fmt[pix_fmt] = {}

            if line.startswith("Size"):
                self.__size()
            else:
                self.__line_idx += 1

    def __size(self):
        """Parse size value (video dimensions)"""

        size = self.formats[self.__line_idx].split()[2]
        # Split size by the "x" in between the dimensions into a tuple
        size = tuple(map(int, size.split("x")))

        last_key = list(self.pix_fmt)[-1]
        self.pix_fmt[last_key][size] = []

        self.__line_idx += 1
        self.__fps()

    def __fps(self):
        """Parse FPS values for size"""

        while self.__line_idx < self.formats_len:
            line = self.formats[self.__line_idx]

            if line.startswith("Interval"):
                # Remove all FPS values that are not a whole number
                if "." in line and ".0" not in line:
                    self.__line_idx += 1
                    continue

                # Capture portion of line with FPS
                fps = line.split()[3]
                # Remove decimals with all zeros and junk opening
                # bracket captured with FPS
                fps = int(fps.split(".")[0].replace("(", ""))

                last_key = list(self.pix_fmt)[-1]
                last_key2 = list(self.pix_fmt[last_key])[-1]
                self.pix_fmt[last_key][last_key2].append(fps)
            else:
                break

            self.__line_idx += 1

    def find_best_format(self):
        """
        Select best video format

        Prefer MJPG over YUV formats
        Prefer 1920x1080 and go down from there
        Prefer 30 FPS and go down from there

        Prioritize at least (cinematic) 24 FPS over a higher resolution
        """

        best_format = "MJPG"
        best_size = (1920, 1080)
        best_fps = 30

        if best_format in self.pix_fmt:
            self.selected_format = best_format
        else:
            # Otherwise, use the first pixel format specified by the webcam
            self.selected_format = self.pix_fmt[0]

        sizes_sorted = self.pix_fmt[self.selected_format].copy()
        sizes_sorted = OrderedDict(sorted(sizes_sorted.items(), reverse=True))

        for size in sizes_sorted:
            if size[0] > best_size[0] or size[1] > best_size[1]:
                continue
            self.selected_size = size

            current_selected_fps = 0
            for fps in sizes_sorted[size]:
                if current_selected_fps < fps <= best_fps:
                    current_selected_fps = fps
            if current_selected_fps >= 24:
                self.selected_fps = current_selected_fps
                break

    def publish_formats_info(self, portid):
        qdb = qubesdb.QubesDB()
        prefix = f"/webcam-devices/{portid}"
        # remove old entries
        qdb.rm(prefix + "/formats/")
        formats = (
                (w, h, fps)
                for pix_fmt, size_dict in self.pix_fmt.items()
                for (w, h), fps_list in size_dict.items()
                for fps in fps_list
                )
        format_nr = 0
        for width, height, fps in sorted(set(formats)):
            qdb.write(f"{prefix}/formats/{format_nr:02d}",
                      f"{width}x{height}x{fps}")
            format_nr += 1


    def configure_webcam_best_format(self):
        """Configure webcam device to use the best format"""

        if (
            self.selected_format == ""
            or self.selected_size == tuple()
            or self.selected_fps == 0
        ):
            self.find_best_format()

        subprocess.run(
            [
                "v4l2-ctl",
                "--device",
                self.video_device,
                "--set-fmt-video",
                "pixelformat="
                + self.selected_format
                + ",width="
                + str(self.selected_size[0])
                + ",height="
                + str(self.selected_size[1]),
            ],
            check=True,
        )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", help="/dev/video* device path")
    parser.add_argument("--portid",
        help="QVC device portid for publishing in qubesdb")
    parser.add_argument("action", help="Action to perform; supported: publish")

    args = parser.parse_args()

    if args.action != "publish":
        parser.error("Unsupported action: " + args.action)

    if args.device and not args.portid:
        parser.error(
            "portid mandatory for publish action, if alternative device is set"
        )

    if not args.device:
        args.device = "/dev/video0"
        args.portid = "dev-video0"

    webcam_supported_formats = (
        subprocess.run(
            ["v4l2-ctl", "--device", args.device, "--list-formats-ext"],
            stdout=subprocess.PIPE,
            check=True,
        )
        .stdout.decode("utf-8")
        .replace("\t", "")
        .splitlines()
    )

    webcam_settings = WebcamFormats(webcam_supported_formats, args.device)
    webcam_settings.publish_formats_info(args.portid)



if __name__ == "__main__":
    main()
