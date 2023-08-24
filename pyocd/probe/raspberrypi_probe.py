# pyOCD debugger
# Copyright (c) 2023 Brian Pugh
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import re
from typing import (Callable, Collection, Optional, overload, Sequence, Set, TYPE_CHECKING, Tuple, Union, List)
from pathlib import Path
from time import sleep
import contextlib
from ..core.plugin import Plugin
from ..core.options import OptionInfo
from .debug_probe import DebugProbe

if TYPE_CHECKING:
    from ..core.session import Session
    from ..core.memory_interface import MemoryInterface
    from ..board.board import Board
    from ..board.board_ids import BoardInfo
    from ..coresight.ap import APAddressBase


LOG = logging.getLogger(__name__)


def is_raspberry_pi():
    with contextlib.suppress():
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Hardware') and ('BCM' in line):
                    return True
    return False


class SpiWrapper:
    def __init__(self, bus: int, device: int):
        from spidev import SpiDev

        self.bus = bus
        self.device = device
        self._spi = SpiDev()
        self.is_open = False

    def open(self):
        self._spi.open(self.bus, self.device)
        self.is_open = True

    def close(self):
        self._spi.close()
        self.is_close = False

    def __enter__(self):
        self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __str__(self):
        return f"/dev/spidev{self.bus}.{self.device}"

    @classmethod
    def from_str(cls, s):
        match = re.match(r'/dev/spidev(\d+)\.(\d+)', s)
        if not match:
            raise ValueError
        bus, device = int(match.group(1)), int(match.group(2))
        return cls(bus, device)

    @classmethod
    def discover_all(cls) -> List["SpiWrapper"]:
        return [cls.from_str(str(port)) for port in Path("/dev").glob("spidev*.*")]

    def set_clock(self, frequency: float):
        self._spi.max_speed_hz = int(frequency)



class RaspberryPiProbe(DebugProbe):
    NRESET_GPIO_OPTION = 'raspberrypiprobe.gpio.nreset'
    DIO_GPIO_OPTION = 'raspberrypiprobe.gpio.dio'
    CLK_GPIO_OPTION = 'raspberrypiprobe.gpio.clk'

    def __init__(self, spi: SpiWrapper):
        import RPi.GPIO as GPIO

        super().__init__()
        GPIO.setmode(GPIO.BCM)

        self._spi = spi
        self._is_connected = False
        self._reset = False  # Record reset_asserted state

    @classmethod
    def get_all_connected_probes(
                cls,
                unique_id: Optional[str] = None,
                is_explicit: bool = False
            ) -> Sequence["DebugProbe"]:
        return [cls(x) for x in SpiWrapper.discover_all()]

    @classmethod
    def get_probe_with_id(cls, unique_id: str, is_explicit: bool = False) -> Optional["DebugProbe"]:
        return cls(SpiWrapper.from_str(unique_id))

    @property
    def vendor_name(self):
        return "Raspberry Pi Foundation"

    @property
    def product_name(self):
        return "Raspberry Pi"

    @ property
    def supported_wire_protocols(self):
        return [DebugProbe.Protocol.DEFAULT, DebugProbe.Protocol.SWD]

    @property
    def unique_id(self) -> str:
        return str(self._spi)

    @property
    def wire_protocol(self) -> Optional[DebugProbe.Protocol]:
        return DebugProbe.Protocol.SWD if self._is_connected else None

    @property
    def is_open(self) -> bool:
        return self._spi.is_open

    @property
    def capabilities(self) -> Set[DebugProbe.Capability]:
        return {DebugProbe.Capability.SWJ_SEQUENCE, DebugProbe.Capability.SWD_SEQUENCE}

    def open(self) -> None:
        self._spi.open()

    def close(self) -> None:
        self._spi.close()

    def connect(self, protocol: Optional[Protocol] = None) -> None:
        """@brief Initialize DAP IO pins for JTAG or SWD"""
        import RPi.GPIO as GPIO

        if (protocol is None) or (protocol == DebugProbe.Protocol.DEFAULT):
            protocol = DebugProbe.Protocol.SWD

        # Validate selected protocol.
        if protocol != DebugProbe.Protocol.SWD:
            raise ValueError("unsupported wire protocol %s" % protocol)

        self._is_connected = True

        GPIO.setup(self.session.options.get(self.NRESET_GPIO_OPTION), GPIO.OUT)

        # Subscribe to option change events
        self.session.options.subscribe(self._change_options, [self.DIO_GPIO_OPTION, self.CLK_GPIO_OPTION])


    def disconnect(self) -> None:
        self._is_connected = False

    def swj_sequence(self, length: int, bits: int) -> None:
        """@brief Transfer some number of bits on SWDIO/TMS.

        @param self
        @param length Number of bits to transfer. Must be less than or equal to 256.
        @param bits Integer of the bit values to send on SWDIO/TMS. The LSB is transmitted first.
        """
        pass

    def swd_sequence(self, sequences: Sequence[Union[Tuple[int], Tuple[int, int]]]) -> Tuple[int, Sequence[bytes]]:
        """@brief Send a sequences of bits on the SWDIO signal.

        Each sequence in the _sequences_ parameter is a tuple with 1 or 2 members in this order:
        - 0: int: number of TCK cycles from 1-64
        - 1: int: the SWDIO bit values to transfer. The presence of this tuple member indicates the sequence is
            an output sequence; the absence means that the specified number of TCK cycles of SWDIO data will be
            read and returned.

        @param self
        @param sequences A sequence of sequence description tuples as described above.

        @return A 2-tuple of the response status, and a sequence of bytes objects, one for each input
            sequence. The length of the bytes object is (<TCK-count> + 7) / 8. Bits are in LSB first order.
        """
        raise NotImplementedError()

    def set_clock(self, frequency: float) -> None:
        self._spi.set_clock(frequency)

    def reset(self) -> None:
        self.assert_reset(True)
        sleep(self.session.options.get('reset.hold_time'))
        self.assert_reset(False)
        sleep(self.session.options.get('reset.post_delay'))

    def assert_reset(self, asserted: bool) -> None:
        import RPi.GPIO as GPIO

        GPIO.output(self.session.options.get(self.NRESET_GPIO_OPTION), False)
        self._reset = asserted

    def is_reset_asserted(self) -> bool:
        """@brief Returns True if nRESET is asserted or False if de-asserted.

        If the debug probe cannot actively read the reset signal, the value returned will be the
        last value passed to assert_reset().
        """
        return self._reset

    def read_dp(self, addr: int, now: bool = True) -> Union[int, Callable[[], int]]:
        raise NotImplementedError

    def write_dp(self, addr: int, data: int) -> None:
        raise NotImplementedError

    def read_ap(self, addr: int, now: bool = True) -> Union[int, Callable[[], int]]:
        raise NotImplementedError

    def write_ap(self, addr: int, data) -> None:
        raise NotImplementedError

    def read_ap_multiple(self, addr: int, count: int = 1, now: bool = True) \
             -> Union[Sequence[int], Callable[[], Sequence[int]]]:
        """@brief Read one AP register multiple times."""
        raise NotImplementedError()

    def write_ap_multiple(self, addr: int, values) -> None:
        """@brief Write one AP register multiple times."""
        raise NotImplementedError()

    def swo_start(self, baudrate: float) -> None:
        """@brief Start receiving SWO data at the given baudrate.

        Once SWO reception has started, the swo_read() method must be called at regular intervals
        to receive SWO data. If this is not done, the probe's internal SWO data buffer may overflow
        and data will be lost.
        """
        raise NotImplementedError()

    def swo_stop(self) -> None:
        """@brief Stop receiving SWO data."""
        raise NotImplementedError()

    def swo_read(self) -> bytearray:
        """@brief Read buffered SWO data from the target.

        @eturn Bytearray of the received data. May be 0 bytes in length if no SWO data is buffered
            at the probe.
        """
        raise NotImplementedError()

    def _change_options(self, notification):
        import RPi.GPIO as GPIO
        if notification.event == self.NRESET_GPIO_OPTION:
            GPIO.setup(self.session.options.get(self.NRESET_GPIO_OPTION), GPIO.OUT)
        elif notification.event == self.DIO_GPIO_OPTION:
            raise NotImplementedError
        elif notification.event == self.CLK_GPIO_OPTION:
            raise NotImplementedError



class RaspberryPiProbePlugin(Plugin):
    """@brief Plugin class for Raspberry Pi GPIO probe."""

    def should_load(self) -> bool:
        """@brief Whether the plugin should be loaded."""
        return is_raspberry_pi()

    def load(self):
        return RaspberryPiProbe

    @ property
    def name(self):
        return "raspberrypiprobe"

    @ property
    def description(self):
        return "Raspberry Pi GPIO Probe"

    @ property
    def options(self):
        """@brief Returns picoprobe options."""
        return [
            OptionInfo(RaspberryPiProbe.NRESET_GPIO_OPTION,
                       int,
                       23,
                       "GPIO number (not physical pin) for SWCLK."
                       ),
            OptionInfo(RaspberryPiProbe.DIO_GPIO_OPTION,
                       int,
                       24,
                       "GPIO number (not physical pin) for SWDIO."
                       ),
            OptionInfo(RaspberryPiProbe.DIO_GPIO_OPTION,
                       int,
                       25,
                       "GPIO number (not physical pin) for SWCLK."
                       ),
        ]
