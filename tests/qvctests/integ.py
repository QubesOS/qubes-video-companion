import unittest
from math import sqrt

import qubes.tests.extra


class TC_00_QVCTest(qubes.tests.extra.ExtraTestCase):
    def setUp(self):
        super(TC_00_QVCTest, self).setUp()
        self.screenshare, self.proxy, self.view = self.create_vms(
            ["share", "proxy", "view"])
        self.screenshare.start()
        if self.screenshare.run('which qubes-video-companion', wait=True) != 0:
            self.skipTest('qubes-video-companion not installed')

    def wait_for_video0(self, vm):
        vm.run(
            'for i in `seq 30`; do '
            '  [ -e /dev/video0 ] && break; '
            '  sleep 0.5; '
            'done; sleep 1', wait=True)

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

    def capture_from_video(self, vm):
        # capture in destination, use gstreamer as it is installed already:
        gst_command = (
            'gst-launch-1.0 --quiet v4l2src num-buffers=1 '
            '! videoconvert '
            '! video/x-raw,format=RGB '
            '! fdsink'
        )
        return vm.run(
            gst_command, passio_popen=True).communicate()[0]

    def capture_from_screen(self, vm):
        return vm.run(
            'import -window root -depth 8 rgb:-', passio_popen=True)\
            .communicate()[0]

    def compare_images(self, img1, img2):
        """Compare images (array of RGB pixels), return similarity factor -
        the lower the better"""

        assert len(img1) == len(img2)
        sum2 = 0
        for p1, p2 in zip(img1, img2):
            sum2 += (p1-p2)**2

        return sqrt(sum2/len(img1))

    def test_010_screenshare(self):
        self.view.start()
        self.qrexec_policy('qvc.ScreenShare',
                           self.view.name,
                           '@default',
                           target=self.screenshare.name)
        p = self.view.run('qubes-video-companion screenshare',
                           passio_popen=True)
        # wait for device to appear, or a timeout
        self.wait_for_video0(self.view)
        self.assertIsNone(p.returncode)

        # capture in source:
        source_image = self.capture_from_screen(self.screenshare)
        destination_image = self.capture_from_video(self.view)
        diff = self.compare_images(source_image, destination_image)
        self.assertLess(diff, 2.0)
        self.click_stop(self.screenshare, 'screenshare')
        # wait for device to disappear, or a timeout
        self.wait_for_video0_disconnect(self.view)
        self.assertEqual(p.wait(), 0)

    # qvc.Webcam is not happy about "camera" created by qvc.ScreenShare
    @unittest.expectedFailure
    def test_020_webcam(self):
        """Two stages test: screen share and then webcam

        screenshare -> proxy (screenshare), then proxy -> view (webcam)
        """
        self.proxy.start()
        self.view.start()
        self.qrexec_policy('qvc.ScreenShare',
                           self.proxy.name,
                           '@default',
                           target=self.screenshare.name)
        self.qrexec_policy('qvc.Webcam',
                           self.view.name,
                           '@default',
                           target=self.proxy.name)
        p = self.proxy.run('qubes-video-companion screenshare',
                           passio_popen=True)
        # wait for device to appear, or a timeout
        self.wait_for_video0(self.proxy)
        self.assertIsNone(p.returncode)
        p2 = self.view.run('qubes-video-companion webcam',
                           passio_popen=True)
        self.wait_for_video0(self.view)
        self.assertIsNone(p2.returncode)

        source_image = self.capture_from_screen(self.screenshare)
        destination_image = self.capture_from_video(self.view)
        diff = self.compare_images(source_image, destination_image)
        self.assertLess(diff, 2.0)
        self.click_stop(self.view, 'webcam')
        self.click_stop(self.screenshare, 'screenshare')
        self.wait_for_video0_disconnect(self.proxy)
        self.assertEqual(p2.wait(), 0)
        self.assertEqual(p.wait(), 0)


def list_tests():
    return (
        TC_00_QVCTest,
    )
