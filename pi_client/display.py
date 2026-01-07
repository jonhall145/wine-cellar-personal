"""
LCD Display manager for Raspberry Pi wine cellar.

Supports Freenove I2C LCD 1602 (16x2 character display) with PCF8574 I2C expander.
"""

import time
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class DisplayState(Enum):
    """Display states for workflow feedback."""
    IDLE = "idle"
    SCANNING = "scanning"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class DisplayConfig:
    """LCD display configuration."""
    i2c_address: int = 0x27  # Common PCF8574 address (some use 0x3F)
    i2c_bus: int = 1  # Pi uses bus 1
    cols: int = 16
    rows: int = 2
    backlight: bool = True


# LCD commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

# Flags for display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

# Flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

# Flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10DOTS = 0x04
LCD_5x8DOTS = 0x00

# Flags for backlight control
LCD_BACKLIGHT = 0x08
LCD_NOBACKLIGHT = 0x00

# PCF8574 bit positions
EN = 0b00000100  # Enable bit
RW = 0b00000010  # Read/Write bit
RS = 0b00000001  # Register select bit


class DisplayManager:
    """
    Manager for I2C LCD 1602 display.

    Provides simple interface for showing status messages during
    wine cellar operations.
    """

    def __init__(self, config: Optional[DisplayConfig] = None):
        """
        Initialize display manager.

        Args:
            config: Display configuration, or None for defaults
        """
        self.config = config or DisplayConfig()
        self._bus = None
        self._backlight_state = LCD_BACKLIGHT if self.config.backlight else LCD_NOBACKLIGHT
        self._display_function = LCD_4BITMODE | LCD_2LINE | LCD_5x8DOTS
        self._display_control = LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF
        self._display_mode = LCD_ENTRYLEFT | LCD_ENTRYSHIFTDECREMENT
        self._initialized = False

        self._init_display()

    def _init_display(self) -> None:
        """Initialize I2C bus and LCD."""
        try:
            import smbus2
            self._bus = smbus2.SMBus(self.config.i2c_bus)
        except ImportError:
            try:
                import smbus
                self._bus = smbus.SMBus(self.config.i2c_bus)
            except ImportError:
                print("Warning: smbus2/smbus not available - display disabled")
                return
        except Exception as e:
            print(f"Warning: Failed to open I2C bus: {e}")
            return

        # LCD initialization sequence (HD44780)
        time.sleep(0.05)  # Wait for LCD to power up

        # Put LCD into 4-bit mode
        self._write4bits(0x03 << 4)
        time.sleep(0.005)
        self._write4bits(0x03 << 4)
        time.sleep(0.005)
        self._write4bits(0x03 << 4)
        time.sleep(0.001)
        self._write4bits(0x02 << 4)  # Finally, set to 4-bit interface

        # Set number of lines and font
        self._command(LCD_FUNCTIONSET | self._display_function)

        # Turn display on
        self._command(LCD_DISPLAYCONTROL | self._display_control)

        # Clear display
        self.clear()

        # Set entry mode
        self._command(LCD_ENTRYMODESET | self._display_mode)

        self._initialized = True

    def _write4bits(self, data: int) -> None:
        """Write 4 bits to LCD via I2C."""
        if self._bus is None:
            return
        try:
            self._bus.write_byte(self.config.i2c_address, data | self._backlight_state)
            self._strobe(data)
        except Exception:
            pass

    def _strobe(self, data: int) -> None:
        """Toggle enable pin to latch data."""
        if self._bus is None:
            return
        try:
            self._bus.write_byte(
                self.config.i2c_address,
                data | EN | self._backlight_state
            )
            time.sleep(0.0005)
            self._bus.write_byte(
                self.config.i2c_address,
                (data & ~EN) | self._backlight_state
            )
            time.sleep(0.0001)
        except Exception:
            pass

    def _write(self, cmd: int, mode: int = 0) -> None:
        """Write a command or data byte to LCD."""
        high = mode | (cmd & 0xF0)
        low = mode | ((cmd << 4) & 0xF0)
        self._write4bits(high)
        self._write4bits(low)

    def _command(self, cmd: int) -> None:
        """Send command to LCD."""
        self._write(cmd, 0)

    def _data(self, data: int) -> None:
        """Send data to LCD."""
        self._write(data, RS)

    def clear(self) -> None:
        """Clear display and return cursor home."""
        self._command(LCD_CLEARDISPLAY)
        time.sleep(0.002)

    def home(self) -> None:
        """Return cursor to home position."""
        self._command(LCD_RETURNHOME)
        time.sleep(0.002)

    def set_cursor(self, col: int, row: int) -> None:
        """Set cursor position."""
        row_offsets = [0x00, 0x40, 0x14, 0x54]
        if row >= self.config.rows:
            row = self.config.rows - 1
        self._command(LCD_SETDDRAMADDR | (col + row_offsets[row]))

    def set_backlight(self, on: bool) -> None:
        """Turn backlight on or off."""
        self._backlight_state = LCD_BACKLIGHT if on else LCD_NOBACKLIGHT
        if self._bus is not None:
            try:
                self._bus.write_byte(self.config.i2c_address, self._backlight_state)
            except Exception:
                pass

    def write_string(self, text: str) -> None:
        """Write string at current cursor position."""
        for char in text:
            self._data(ord(char))

    def write_line(self, row: int, text: str, center: bool = False) -> None:
        """
        Write text to a specific row.

        Args:
            row: Row number (0 or 1)
            text: Text to display
            center: Center the text if True
        """
        # Truncate or pad to display width
        text = text[:self.config.cols]
        if center:
            text = text.center(self.config.cols)
        else:
            text = text.ljust(self.config.cols)

        self.set_cursor(0, row)
        self.write_string(text)

    def show_message(self, line1: str, line2: str = "") -> None:
        """
        Show a two-line message.

        Args:
            line1: First line text
            line2: Second line text
        """
        self.write_line(0, line1)
        self.write_line(1, line2)

    def show_status(self, state: DisplayState, message: str = "") -> None:
        """
        Show status with appropriate formatting.

        Args:
            state: Current display state
            message: Additional message text
        """
        status_messages = {
            DisplayState.IDLE: ("Wine Cellar", "Ready"),
            DisplayState.SCANNING: ("Scanning...", "Hold bottle steady"),
            DisplayState.PROCESSING: ("Processing...", "Please wait"),
            DisplayState.SUCCESS: ("Success!", message or "Operation complete"),
            DisplayState.ERROR: ("Error", message or "Try again"),
            DisplayState.OFFLINE: ("Offline Mode", "Queued for sync"),
        }

        line1, line2 = status_messages.get(state, ("", ""))
        if state in (DisplayState.SUCCESS, DisplayState.ERROR) and message:
            line2 = message

        self.show_message(line1, line2)

    def show_wine_added(self, wine_name: str, position: str = "") -> None:
        """Show wine added confirmation."""
        # Truncate wine name if needed
        name = wine_name[:self.config.cols]
        if position:
            self.show_message(f"Added: {name}", f"Pos: {position}")
        else:
            self.show_message("Added:", name)

    def show_wine_removed(self, wine_name: str, position: str = "") -> None:
        """Show wine removed confirmation."""
        name = wine_name[:self.config.cols]
        if position:
            self.show_message(f"Removed: {name}", f"From: {position}")
        else:
            self.show_message("Removed:", name)

    def show_barcode_found(self, barcode: str) -> None:
        """Show detected barcode."""
        self.show_message("Barcode found:", barcode[:self.config.cols])

    def show_unknown_wine(self) -> None:
        """Show prompt for unknown wine."""
        self.show_message("Unknown wine", "Capture label...")

    def show_position_detected(self, row: int, col: int) -> None:
        """Show detected rack position."""
        self.show_message("Position found:", f"Row {row+1}, Col {col+1}")

    def show_sync_status(self, pending: int, synced: int = 0) -> None:
        """Show sync queue status."""
        if pending > 0:
            self.show_message("Sync pending", f"{pending} operations")
        else:
            self.show_message("Synced", f"{synced} operations")

    def show_error(self, error: str) -> None:
        """Show error message."""
        # Split error across two lines if needed
        if len(error) <= self.config.cols:
            self.show_message("Error:", error)
        else:
            self.show_message(error[:self.config.cols], error[self.config.cols:self.config.cols*2])

    def close(self) -> None:
        """Clean up display resources."""
        if self._initialized:
            self.clear()
            self.set_backlight(False)
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
            self._bus = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class MockDisplayManager:
    """
    Mock display manager for testing without hardware.

    Prints messages to console instead of LCD.
    """

    def __init__(self, config: Optional[DisplayConfig] = None):
        self.config = config or DisplayConfig()
        self._line1 = ""
        self._line2 = ""
        print("[Display] Mock display initialized")

    def clear(self) -> None:
        self._line1 = ""
        self._line2 = ""
        print("[Display] Cleared")

    def show_message(self, line1: str, line2: str = "") -> None:
        self._line1 = line1
        self._line2 = line2
        print(f"[Display] {line1}")
        if line2:
            print(f"[Display] {line2}")

    def show_status(self, state: DisplayState, message: str = "") -> None:
        print(f"[Display] Status: {state.value} - {message}")

    def show_wine_added(self, wine_name: str, position: str = "") -> None:
        print(f"[Display] Added: {wine_name} at {position}")

    def show_wine_removed(self, wine_name: str, position: str = "") -> None:
        print(f"[Display] Removed: {wine_name} from {position}")

    def show_barcode_found(self, barcode: str) -> None:
        print(f"[Display] Barcode: {barcode}")

    def show_unknown_wine(self) -> None:
        print("[Display] Unknown wine - capture label")

    def show_position_detected(self, row: int, col: int) -> None:
        print(f"[Display] Position: Row {row+1}, Col {col+1}")

    def show_sync_status(self, pending: int, synced: int = 0) -> None:
        print(f"[Display] Sync: {pending} pending, {synced} synced")

    def show_error(self, error: str) -> None:
        print(f"[Display] Error: {error}")

    def close(self) -> None:
        print("[Display] Closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_display(use_mock: bool = False) -> DisplayManager:
    """
    Get appropriate display manager.

    Args:
        use_mock: Force mock display (for testing)

    Returns:
        DisplayManager or MockDisplayManager instance
    """
    if use_mock:
        return MockDisplayManager()

    try:
        display = DisplayManager()
        if display._initialized:
            return display
        else:
            print("Falling back to mock display")
            return MockDisplayManager()
    except Exception as e:
        print(f"Display init failed: {e}, using mock")
        return MockDisplayManager()
