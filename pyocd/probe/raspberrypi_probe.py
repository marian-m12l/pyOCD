import logging
from typing import (Callable, Collection, Optional, overload, Sequence, Set, TYPE_CHECKING, Tuple, Union)
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

class RaspberryPiProbe(DebugProbe):
    DIO_GPIO_OPTION = 'raspberrypiprobe.gpio.dio'
    CLK_GPIO_OPTION = 'raspberrypiprobe.gpio.clk'

    def __init__(self):
        super(self).__init__()

    @classmethod
    def get_all_connected_probes(
                cls,
                unique_id: Optional[str] = None,
                is_explicit: bool = False
            ) -> Sequence["DebugProbe"]:

        raise NotImplementedError

    @classmethod
    def get_probe_with_id(cls, unique_id: str, is_explicit: bool = False) -> Optional["DebugProbe"]:
        raise NotImplementedError

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
        """@brief The unique ID of this device.

        This property will be valid before open() is called. This value can be passed to
        get_probe_with_id().
        """
        return "GPIO"

    @property
    def wire_protocol(self) -> Optional[DebugProbe.Protocol]:
        """@brief Currently selected wire protocol.

        If the probe is not open and connected, i.e., open() and connect() have not been called,
        then this property will be None. If a value other than None is returned, then the probe
        has been connected successfully.
        """
        raise NotImplementedError()

    @property
    def is_open(self) -> bool:
        """@brief Whether the probe is currently open.

        To open the probe, call the open() method.
        """
        raise NotImplementedError()

    @property
    def capabilities(self) -> Set[DebugProbe.Capability]:
        """@brief A set of DebugProbe.Capability enums indicating the probe's features.

        This value should not be trusted until after the probe is opened.
        """
        raise NotImplementedError()

    @property
    def associated_board_info(self) -> Optional["BoardInfo"]:
        """@brief Info about the board associated with this probe, if known."""
        return None

    def get_accessible_pins(self, group: DebugProbe.PinGroup) -> Tuple[int, int]:
        """@brief Return masks of pins accessible via the .read_pins()/.write_pins() methods.

        This method is only expected to be implemented if Capability.PIN_ACCESS is present.

        @return Tuple of pin masks for (0) readable, (1) writable pins. See DebugProbe.Pin for mask
        values for those pins that have constants.
        """
        raise NotImplementedError()

    def open(self) -> None:
        """@brief Open the USB interface to the probe for sending commands."""
        raise NotImplementedError()

    def close(self) -> None:
        """@brief Close the probe's USB interface."""
        raise NotImplementedError()

    def connect(self, protocol: Optional[Protocol] = None) -> None:
        """@brief Initialize DAP IO pins for JTAG or SWD"""
        raise NotImplementedError()

    def disconnect(self) -> None:
        """@brief Deinitialize the DAP I/O pins"""
        raise NotImplementedError()

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
        """@brief Set the frequency for JTAG and SWD in Hz.

        This function is safe to call before connect is called.
        """
        raise NotImplementedError()

    def reset(self) -> None:
        """@brief Perform a hardware reset of the target."""
        raise NotImplementedError()

    def assert_reset(self, asserted: bool) -> None:
        """@brief Assert or de-assert target's nRESET signal.

        Because nRESET is negative logic and usually open drain, passing True will drive it low, and
        passing False will stop driving so nRESET will be pulled up.
        """
        raise NotImplementedError()

    def is_reset_asserted(self) -> bool:
        """@brief Returns True if nRESET is asserted or False if de-asserted.

        If the debug probe cannot actively read the reset signal, the value returned will be the
        last value passed to assert_reset().
        """
        raise NotImplementedError()

    def read_pins(self, group: DebugProbe.PinGroup, mask: int) -> int:
        """@brief Read values of selected debug probe pins.

        See DebugProbe.ProtocolPin for mask values for the DebugProbe.PinGroup.PROTOCOL_PINS group.

        This method is only expected to be implemented if Capability.PIN_ACCESS is present.

        @param self
        @param group Select the pin group to read.
        @param mask Bit mask indicating which pins will be read. The return value will contain only
            bits set in this mask.
        @return Bit mask with the current value of selected pins at each pin's relevant bit position.
        """
        raise NotImplementedError()

    def write_pins(self, group: DebugProbe.PinGroup, mask: int, value: int) -> None:
        """@brief Set values of selected debug probe pins.

        See DebugProbe.ProtocolPin for mask values for the DebugProbe.PinGroup.PROTOCOL_PINS group.
        Note that input-only pins such as TDO are not writable with most debug probes.

        This method is only expected to be implemented if Capability.PIN_ACCESS is present.

        @param self
        @param group Select the pin group to read.
        @param mask Bit mask indicating which pins will be written.
        @param value Mask containing the bit value of to written for selected pins at each pin's
            relevant bit position..
        """
        raise NotImplementedError()


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



class RaspberryPiProbePlugin(Plugin):
    """@brief Plugin class for Raspberry Pi GPIO probe."""

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
            OptionInfo(RaspberryPiProbe.DIO_GPIO_OPTION,
                       int,
                       18,
                       "GPIO number (not physical pin) for SWDIO."
                       ),
            OptionInfo(RaspberryPiProbe.DIO_GPIO_OPTION,
                       int,
                       22,
                       "GPIO number (not physical pin) for SWCLK."
                       ),
        ]
