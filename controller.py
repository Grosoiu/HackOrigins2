import usb_hid
import supervisor
import sys
from adafruit_hid.mouse import Mouse
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

mouse = Mouse(usb_hid.devices)
keyboard = Keyboard(usb_hid.devices)

while True:
    if supervisor.runtime.serial_bytes_available:
        cmd = sys.stdin.readline().strip()

        if cmd.startswith("MOVE"):
            _, x, y = cmd.split(",")
            mouse.move(x=int(x), y=int(y))

        elif cmd == "CLICK":
            mouse.click(Mouse.LEFT_BUTTON)

        elif cmd == "LEFT_DOWN":
            mouse.press(Mouse.LEFT_BUTTON)

        elif cmd == "LEFT_UP":
            mouse.release(Mouse.LEFT_BUTTON)

        elif cmd == "RIGHT_CLICK":
            mouse.click(Mouse.RIGHT_BUTTON)

        elif cmd == "RIGHT_DOWN":
            mouse.press(Mouse.RIGHT_BUTTON)

        elif cmd == "RIGHT_UP":
            mouse.release(Mouse.RIGHT_BUTTON)

        elif cmd == "SHIFT_DOWN":
            keyboard.press(Keycode.SHIFT)
            
        elif cmd == "SHIFT_UP":
            keyboard.release(Keycode.SHIFT)

        elif cmd.startswith("KEY"):
            _, k = cmd.split(",")
            try:
                keyboard.send(getattr(Keycode, k))
            except AttributeError:
                pass  # tasta necunoscuta, ignora