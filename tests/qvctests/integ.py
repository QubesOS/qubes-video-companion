import asyncio
import unittest
from math import sqrt

import qubes.tests.extra


class TC_00_QVCTest(qubes.tests.extra.ExtraTestCase):
    def setUp(self):
        super(TC_00_QVCTest, self).setUp()
        if "webcam" in self.id() and "whonix" in str(self.template):
            self.skipTest("Cannot load 'vivid' module on Whonix")
        self.source, self.view = self.create_vms(
            ["source", "view"])
        self.source.start()
        if self.source.run('which qubes-video-companion', wait=True) != 0:
            self.skipTest('qubes-video-companion not installed')

    def wait_for_video0(self, vm):
        retcode = vm.run(
            'for i in `seq 30`; do '
            '  v4l2-ctl --list-formats /dev/video0 2>/dev/null | grep -F "[0]" && break; '
            '  sleep 0.5; '
            'done; sleep 1; test -e /dev/video0', wait=True)
        self.assertEqual(retcode, 0,
                         f"Timeout waiting for /dev/video0 in {vm.name}")

    def wait_for_video0_disconnect(self, vm):
        vm.run(
            'for i in `seq 30`; do '
            '  ! [ -e /dev/video0 ] && break; '
            '  sleep 0.5; '
            'done', wait=True)
        self.assertNotEqual(vm.run('test -e /dev/video0', wait=True), 0)

    def click_stop(self, vm, name):
        # open context menu
        vm.run('xdotool search --onlyvisible "{}" '
               'mousemove -w %1 5 5 '
               'click 1'.format(name), wait=True)
        # send keys in separate call, to not send them just to the icon window
        vm.run('xdotool key Up Return', wait=True)

    def capture_from_video(self, vm, extra_caps=""):
        # capture in destination, use gstreamer as it is installed already:
        gst_command = (
            'gst-launch-1.0 --quiet v4l2src num-buffers=1 '
            '! videoconvert '
            f'! video/x-raw,format=I420{extra_caps} '
            '! fdsink'
        )
        return vm.run(
            gst_command, passio_popen=True).communicate()[0]

    def capture_from_screen(self, vm):
        gst_command = (
            'gst-launch-1.0 --quiet ximagesrc num-buffers=1 '
            '! capsfilter caps=video/x-raw,format=BGRx,colorimetry=2:4:7:1 '
            '! videoconvert '
            '! video/x-raw,format=I420 '
            '! fdsink'
        )
        return vm.run(
            gst_command, passio_popen=True).communicate()[0]

    def compare_images(self, img1, img2):
        """Compare images (array of RGB pixels), return similarity factor -
        the lower the better"""

        self.assertEqual(len(img1), len(img2))
        sum2 = 0
        for p1, p2 in zip(img1, img2):
            sum2 += (p1-p2)**2

        return sqrt(sum2/len(img1))

    def test_010_screenshare(self):
        self.view.start()
        self.qrexec_policy('qvc.ScreenShare',
                           self.view.name,
                           '@default',
                           target=self.source.name)
        p = self.view.run('qubes-video-companion screenshare',
                           passio_popen=True, passio_stderr=True)
        # wait for device to appear, or a timeout
        self.wait_for_video0(self.view)
        self.loop.run_until_complete(self.wait_for_session(self.view))
        if p.returncode is not None:
            self.fail("'qubes-video-companion screenshare' exited early ({}): {} {}".format(
                        p.returncode, *p.communicate()))

        # capture in source:
        source_image = self.capture_from_screen(self.source)
        destination_image = self.capture_from_video(self.view)
        diff = self.compare_images(source_image, destination_image)
        if diff >= 2.0:
            with open(f"/tmp/window-dump-{self.id()}-source", "wb") as f:
                f.write(source_image)
            with open(f"/tmp/window-dump-{self.id()}-dest", "wb") as f:
                f.write(destination_image)
        self.assertLess(diff, 2.0)
        self.click_stop(self.source, 'screenshare')
        # wait for device to disappear, or a timeout
        self.wait_for_video0_disconnect(self.view)
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            self.fail("'qubes-video-companion screenshare' failed ({}): {} {}".format(
                        p.returncode, stdout, stderr))
        else:
            # just print
            print(stdout)
            print(stderr)

    def apply_mask(self, image, width=640, height=480):
        """Mask dynamic parts of vivid device output

        There are two:
         - timestamp at 16,16 -> 170,32
         - counter + text movement at 16,96 -> 420,116

        The image is assumed to be in I420 format. The mask is applied to
        luminance channel only (which is the first 640*480 bytes).
        """

        image = list(image)

        def fill_black(x1, y1, x2, y2):
            for y in range(y1, y2):
                start = y*width+x1
                end = y*width+x2
                image[start:end] = bytes(end-start)
        fill_black(16, 16, 170, 32)
        fill_black(16, 96, 420, 116)

        return bytes(image)


    def test_020_webcam(self):
        """Webcam test

        source -> view (webcam)
        """
        self.loop.run_until_complete(self.wait_for_session(self.source))
        self.view.start()
        self.loop.run_until_complete(self.wait_for_session(self.view))
        self.qrexec_policy('qvc.Webcam',
                           self.view.name,
                           '@default',
                           target=self.source.name)
        ret = self.source.run("modprobe vivid", user="root", wait=True)
        if ret != 0:
            self.skipTest("Cannot load 'vivid' module")
        # wait for device to appear, or a timeout
        self.wait_for_video0(self.source)

        p2 = self.view.run('qubes-video-companion -r 640x480x30 webcam',
                           passio_popen=True, passio_stderr=True)
        self.wait_for_video0(self.view)
        if p2.returncode is not None:
            self.fail("'qubes-video-companion webcam' exited early ({}): {} {}".format(
                        p2.returncode, *p2.communicate()))

        destination_image = self.capture_from_video(self.view)
        destination_image = self.apply_mask(destination_image)
        self.click_stop(self.source, 'webcam')
        self.wait_for_video0_disconnect(self.view)
        stdout, stderr = p2.communicate()
        if p2.returncode != 0:
            self.fail("'qubes-video-companion webcam' failed ({}): {} {}".format(
                        p2.returncode, stdout, stderr))
        else:
            # just print
            print(stdout)
            print(stderr)

        # vivid supports only one client at a time, so capture source only
        # after QVC disconnects
        source_image = self.capture_from_video(self.source, ",width=640,height=480")
        source_image = self.apply_mask(source_image)
        diff = self.compare_images(source_image, destination_image)
        if diff >= 2.5:
            with open(f"/tmp/window-dump-{self.id()}-source", "wb") as f:
                f.write(source_image)
            with open(f"/tmp/window-dump-{self.id()}-dest", "wb") as f:
                f.write(destination_image)
        self.assertLess(diff, 2.5)


def list_tests():
    return (
        TC_00_QVCTest,
    )
