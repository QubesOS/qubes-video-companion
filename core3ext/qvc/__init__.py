# Copyright (C) 2025 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
# Licensed under the MIT License. See LICENSE file for details.
import asyncio
import contextlib
import os
import re
import string
import subprocess
from typing import Optional, List

import qubes.device_protocol
import qubes.ext
from qubes.device_protocol import DeviceInterface, Port
from qubes.exc import QubesException
from qubes.ext import utils
from qubes.utils import sanitize_stderr_for_log

name_re = re.compile(r"\A[a-z0-9-]{1,12}\Z")
device_re = re.compile(r"\A[a-z0-9/-]{1,64}\Z")
connected_to_re = re.compile(rb"^[a-zA-Z][a-zA-Z0-9_.-]*$")


class WebcamDevice(qubes.device_protocol.DeviceInfo):
    def __init__(self, port: qubes.device_protocol.Port):
        if port.devclass != "webcam":
            raise qubes.exc.QubesValueError(
                f"Incompatible device class for input port: {port.devclass}"
            )

        # init parent class
        super().__init__(port)

        self._qdb_path = f"/webcam-devices/{port.port_id}"

        # TODO: available res, fps

    @property
    def interfaces(self) -> List[DeviceInterface]:
        return [DeviceInterface("u0e0200")]

    @property
    def vendor(self) -> str:
        if self.parent_device:
            return self.parent_device.vendor
        return "unknown"

    @property
    def manufacturer(self) -> str:
        if self.parent_device:
            return self.parent_device.manufacturer
        return "unknown"

    @property
    def product(self) -> str:
        if self.parent_device:
            return self.parent_device.product
        return "unknown"

    @property
    def name(self) -> str:
        if self.parent_device:
            return f"Camera ({self.parent_device.name})"
        return "Camera"

    @property
    def description(self) -> str:
        if self.parent_device:
            return f"Camera ({self.parent_device.description})"
        return "Camera"

    @property
    def serial(self) -> str:
        if self.parent_device:
            return self.parent_device.serial
        return "unknown"

    @property
    def device_id(self) -> str:
        if self.parent_device:
            return self.parent_device.device_id
        return super().device_id

    @staticmethod
    def _sanitize(
        untrusted_parent: bytes,
        safe_chars: str = string.ascii_letters
        + string.digits
        + string.punctuation,
    ) -> str:
        untrusted_device_desc = untrusted_parent.decode(
            "ascii", errors="ignore"
        )
        return "".join(
            c if c in set(safe_chars) else "_" for c in untrusted_device_desc
        )

    def _get_parent_device(self, port: Port):
        if not port.backend_domain or not port.backend_domain.is_running():
            return None
        untrusted_parent_info = port.backend_domain.untrusted_qdb.read(
            f"/webcam-devices/{port.port_id}/parent"
        )
        if not untrusted_parent_info:
            return None
        parent_devclass, parent_ident = self._sanitize(
            untrusted_parent_info
        ).split(":", maxsplit=1)
        if not parent_ident:
            return None
        try:
            return port.backend_domain.devices[parent_devclass][
                parent_ident
            ]
        except KeyError:
            return qubes.device_protocol.UnknownDevice(
                qubes.device_protocol.Port(
                    port.backend_domain, parent_ident,
                    devclass=parent_devclass
                )
            )
    @property
    def parent_device(self) -> Optional[qubes.device_protocol.DeviceInfo]:
        """
        The parent device, if any.
        """
        if self._parent is None:
            self._parent = self._get_parent_device(self.port)
        return self._parent

    @property
    def attachment(self):
        if not self.backend_domain.is_running():
            return None
        untrusted_connected_to = self.backend_domain.untrusted_qdb.read(
            self._qdb_path + "/connected-to"
        )
        if not untrusted_connected_to:
            return None
        if not connected_to_re.match(untrusted_connected_to):
            self.backend_domain.log.warning(
                f"Device {self.port_id} has invalid chars in connected-to "
                "property"
            )
            return None
        untrusted_connected_to = untrusted_connected_to.decode(
            "ascii", errors="strict"
        )
        try:
            connected_to = self.backend_domain.app.domains[
                untrusted_connected_to
            ]
        except KeyError:
            self.backend_domain.log.warning(
                f"Device {self.port_id} has invalid VM name in connected-to "
                f"property: {untrusted_connected_to}"
            )
            return None
        return connected_to


class QVCNotInstalled(QubesException):
    pass


@contextlib.contextmanager
def allow_qrexec_call(service, arg, source, dest):
    fname = f"/run/qubes/policy.d/10-qvc-{hash((service, arg, source, dest))}.policy"
    with open(fname, "x") as policy:
        policy.write(f"{service} {arg} {source} {dest} allow\n")
    try:
        yield
    finally:
        os.unlink(fname)


class WebcamDeviceExtension(qubes.ext.Extension):
    @qubes.ext.handler("domain-init", "domain-load")
    def on_domain_init_load(self, vm, event):
        """Initialize watching for changes"""
        # pylint: disable=unused-argument
        vm.watch_qdb_path("/webcam-devices")
        if vm.app.vmm.offline_mode:
            self.devices_cache[vm.name] = {}
            return
        if event == "domain-load":
            # avoid building a cache on domain-init, as it isn't fully set yet,
            # and definitely isn't running yet
            current_devices = {
                dev.port_id: dev.attachment
                for dev in self.on_device_list_webcam(vm, None)
            }
            self.devices_cache[vm.name] = current_devices
        else:
            self.devices_cache[vm.name] = {}

    async def attach_and_notify(self, vm, assignment):
        # bypass DeviceCollection logic preventing double attach
        device = assignment.device
        if assignment.mode.value == "ask-to-attach":
            allowed = await utils.confirm_device_attachment(
                device, {vm: assignment}
            )
            allowed = allowed.strip()
            if vm.name != allowed:
                return
        await self.on_device_attach_webcam(
            vm, "device-pre-attach:webcam", device, assignment.options
        )
        await vm.fire_event_async(
            "device-attach:webcam", device=device, options=assignment.options
        )

    def ensure_detach(self, vm, port):
        """
        Run this method if device is no longer detected.

        No additional action required in case of webcam devices.
        """
        pass

    @qubes.ext.handler("domain-qdb-change:/webcam-devices")
    def on_qdb_change(self, vm, event, path):
        """A change in QubesDB means a change in a device list."""
        # pylint: disable=unused-argument
        current_devices = dict(
            (dev.port_id, dev.attachment)
            for dev in self.on_device_list_webcam(vm, None)
        )
        utils.device_list_change(self, current_devices, vm, path, WebcamDevice)

    @staticmethod
    def device_get(vm, port_id):
        untrusted_qubes_device_attrs = vm.untrusted_qdb.list(
            "/webcam-devices/{}/".format(port_id)
        )
        if not untrusted_qubes_device_attrs:
            return None
        return WebcamDevice(
            qubes.device_protocol.Port(
                backend_domain=vm, port_id=port_id, devclass="webcam"
            )
        )

    @qubes.ext.handler("device-list:webcam")
    def on_device_list_webcam(self, vm, event):
        if not vm.is_running() or not hasattr(vm, "untrusted_qdb"):
            return
        untrusted_devices = vm.untrusted_qdb.list("/webcam-devices/")

        untrusted_idents = set(untrusted_path.split("/", 3)[2]
                               for untrusted_path in untrusted_devices)
        for untrusted_ident in untrusted_idents:
            if not name_re.match(untrusted_ident):
                msg = (
                    "%s vm's device path name contains unsafe characters. "
                    "Skipping it."
                )
                vm.log.warning(msg)
                continue

            port_id = untrusted_ident

            device_info = self.device_get(vm, port_id)
            if device_info:
                yield device_info

    @qubes.ext.handler("device-get:webcam")
    def on_device_get_webcam(self, vm, event, port_id):
        # pylint: disable=unused-argument
        if not vm.is_running():
            return

        if vm.untrusted_qdb.list("/webcam-devices/" + port_id):
            yield WebcamDevice(Port(vm, port_id, "webcam"))

    @staticmethod
    def get_all_devices(app):
        for vm in app.domains:
            if not vm.is_running() or not hasattr(vm, "devices"):
                continue

            for dev in vm.devices["webcam"]:
                if isinstance(dev, WebcamDevice):
                    yield dev

    @qubes.ext.handler("device-list-attached:webcam")
    def on_device_list_attached(self, vm, event, **kwargs):
        # pylint: disable=unused-argument
        if not vm.is_running():
            return

        for dev in self.get_all_devices(vm.app):
            if dev.attachment == vm:
                yield (dev, {})

    @qubes.ext.handler("device-pre-attach:webcam")
    async def on_device_pre_attach_webcam(self, vm, event, device, options):
        # pylint: disable=unused-argument

        arg = device.port_id

        # TODO: options for res/fps
        if options:
            raise QubesException("Options not supported")

        if not vm.is_running() or vm.qid == 0:
            # print(f"Qube is not running, skipping attachment of {device}",
            #       file=sys.stderr)
            return

        assert isinstance(device, WebcamDevice)

        if device.attachment:
            raise qubes.exc.DeviceAlreadyAttached(
                f"Device {device} already attached to {device.attachment}"
            )

        if not vm.features.check_with_template("supported-rpc.qvc.WebcamAttach", False):
            raise QVCNotInstalled("qubes-video-companion not installed in the VM")

        # update the cache before the call, to avoid sending duplicated events
        # (one on qubesdb watch and the other by the caller of this method)
        self.devices_cache[device.backend_domain.name][device.port_id] = vm

        # set qrexec policy to allow this device
        with allow_qrexec_call("qvc.Webcam", "+" + arg, f"uuid:{vm.uuid}", f"uuid:{device.backend_domain.uuid}"):
            # and actual attach
            try:
                await vm.run_service_for_stdio(
                    "qvc.WebcamAttach",
                    user="root",
                    input=f"{device.backend_domain.name} "
                    f"{arg}\n".encode(),
                )
            except subprocess.CalledProcessError as e:
                # pylint: disable=raise-missing-from
                if e.returncode == 127:
                    raise QVCNotInstalled("qubes-video-companion not installed in the VM")
                raise QubesException(
                    f"Device attach failed: {sanitize_stderr_for_log(e.output)}"
                    f" {sanitize_stderr_for_log(e.stderr)}"
                )

    @qubes.ext.handler("device-pre-detach:webcam")
    async def on_device_detach_webcam(self, vm, event, port):
        # pylint: disable=unused-argument
        if not vm.is_running() or vm.qid == 0:
            return

        for attached, _options in self.on_device_list_attached(vm, event):
            if attached.port == port:
                break
        else:
            raise QubesException(
                f"Device {port} not connected to VM {vm.name}"
            )

        # update the cache before the call, to avoid sending duplicated events
        # (one on qubesdb watch and the other by the caller of this method)
        backend = attached.backend_domain
        self.devices_cache[backend.name][attached.port_id] = None

        try:
            await backend.run_service_for_stdio(
                f"qvc.WebcamDetach+{attached.port_id}",
                user="root",
            )
        except subprocess.CalledProcessError as e:
            # pylint: disable=raise-missing-from
            raise QubesException(
                f"Device detach failed: {sanitize_stderr_for_log(e.output)}"
                f" {sanitize_stderr_for_log(e.stderr)}"
            )

    @qubes.ext.handler("device-pre-assign:webcam")
    async def on_device_assign_webcam(self, vm, event, device, options):
        # pylint: disable=unused-argument
        pass
        # TODO: verify options

    @qubes.ext.handler("domain-start")
    async def on_domain_start(self, vm, _event, **_kwargs):
        # pylint: disable=unused-argument
        to_attach = {}
        assignments = vm.devices["webcam"].get_assigned_devices()
        # the most specific assignments first
        for assignment in reversed(sorted(assignments)):
            for device in assignment.devices:
                if isinstance(device, qubes.device_protocol.UnknownDevice):
                    continue
                if device.attachment:
                    continue
                if not assignment.matches(device):
                    vm.log.warning(
                        "Unrecognized identity, skipping attachment of device "
                        f"from the port {assignment}",
                    )
                    continue
                # chose first assignment (the most specific) and ignore rest
                if device not in to_attach:
                    # make it unique
                    to_attach[device] = assignment.clone(device=device)
        in_progress = set()
        for assignment in to_attach.values():
            in_progress.add(
                asyncio.ensure_future(self.attach_and_notify(vm, assignment))
            )
        if in_progress:
            await asyncio.wait(in_progress)

    @qubes.ext.handler("domain-shutdown")
    async def on_domain_shutdown(self, vm, _event, **_kwargs):
        # pylint: disable=unused-argument
        vm.fire_event("device-list-change:webcam")
        utils.device_list_change(self, {}, vm, None, WebcamDevice)

    @qubes.ext.handler("qubes-close", system=True)
    def on_qubes_close(self, app, event):
        # pylint: disable=unused-argument
        self.devices_cache.clear()
