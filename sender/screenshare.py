#!/usr/bin/python3 --

# Copyright (C) 2021 Elliot Killick <elliotkillick@zohomail.eu>
# Copyright (C) 2021 Demi Marie Obenour <demi@invisiblethingslab.com>
# Copyright (C) 2024 Benjamin Grande M. S. <ben.grande.b@gmail.com>
# Licensed under the MIT License. See LICENSE file for details.

"""Screen sharing video source module"""

# GI requires version declaration before importing
# pylint: disable=wrong-import-position

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf
from service import Service
from typing import List, Tuple


class ScreenShare(Service):
    """Screen sharing video souce class"""

    def __init__(self) -> None:
        self.selected_monitor_index = None
        self.main(self)

    def video_source(self) -> str:
        return "screenshare"

    def icon(self) -> str:
        return "video-display"

    def monitor_dialog(self) -> None:
        display = Gdk.Display().get_default()
        monitor_count = display.get_n_monitors()

        if monitor_count == 1:
            self.selected_monitor_index = 0
            return

        combobox = Gtk.ComboBoxText()
        monitor_screenshots = []
        for monitor_num in range(monitor_count):
            monitor_name = display.get_monitor(monitor_num).get_model()
            monitor = display.get_monitor(monitor_num)
            monitor_geometry = monitor.get_geometry()
            monitor_width = monitor_geometry.width
            monitor_height = monitor_geometry.height
            monitor_x = monitor_geometry.x
            monitor_y = monitor_geometry.y

            combobox.append_text(f"{monitor_name}: "
                                 f"{monitor_width}x{monitor_height} "
                                 f"{monitor_x}+{monitor_y}")

            pixbuf = Gdk.pixbuf_get_from_window(
                display.get_default_screen().get_root_window(),
                monitor_x,
                monitor_y,
                monitor_width,
                monitor_height)
            pixbuf = pixbuf.scale_simple(
                min(960, pixbuf.get_width()),
                min(540, pixbuf.get_height()),
                GdkPixbuf.InterpType.BILINEAR)
            monitor_screenshots.append(pixbuf)

        window = Gtk.Window(title="Qubes Screen Share")
        window.connect("destroy", Gtk.main_quit)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        window.add(vbox)

        ## TODO: add 'remote_domain' to differentiate calls.
        label = Gtk.Label(label="Select a monitor:")
        vbox.pack_start(label, False, False, 0)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(hbox, False, False, 0)

        ## Select first monitor when opening the dialog.
        combobox.set_active(0)

        hbox.pack_start(combobox, True, True, 0)
        ok_button = Gtk.Button(label="OK")
        cancel_button = Gtk.Button(label="Cancel")
        hbox.pack_end(ok_button, False, False, 0)
        hbox.pack_end(cancel_button, False, False, 0)

        def on_ok_button_clicked(_):
            self.selected_monitor_index = combobox.get_active()
            window.close()

        def on_cancel_button_clicked(_):
            window.close()

        ok_button.connect("clicked", on_ok_button_clicked)
        cancel_button.connect("clicked", on_cancel_button_clicked)

        image = Gtk.Image()
        vbox.pack_start(image, True, True, 0)

        def on_combobox_changed(combobox):
            monitor_index = combobox.get_active()
            pixbuf = monitor_screenshots[monitor_index]
            image.set_from_pixbuf(pixbuf)

        combobox.connect("changed", on_combobox_changed)
        ## Show the first monitor screenshot when opening the dialog.
        on_combobox_changed(combobox)

        window.show_all()
        Gtk.main()

    def parameters(self) -> Tuple[int, int, int]:
        display = Gdk.Display().get_default()
        self.monitor_dialog()
        monitor_index = self.selected_monitor_index
        if monitor_index is None:
            raise ValueError("Monitor index was not set")
        geometry = display.get_monitor(monitor_index).get_geometry()
        screen = Gdk.Screen().get_default()
        kwargs = {
            "crop_t": geometry.y,
            "crop_l": geometry.x,
            "crop_r": screen.width()  - geometry.x - geometry.width,
            "crop_b": screen.height() - geometry.y - geometry.height,
        }
        return (geometry.width, geometry.height, 30, kwargs)

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
