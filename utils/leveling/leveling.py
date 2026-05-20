import serial
import time
import threading

PORT = "COM3"
BAUDRATE = 115200
SPACE_KEY = "SPACEBAR"

print(f"Connecting to {PORT}...")
try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=1)
    time.sleep(2)
    print("Connected.")
except Exception as exc:
    print(f"Failed to connect: {exc}")
    raise SystemExit(1)

serial_lock = threading.Lock()

def send_command(cmd):
    """Send a command to the microcontroller."""
    with serial_lock:
        ser.write((cmd + "\n").encode())

def main():
    time.sleep(5)
    try:
        print("Pressing SPACE every 200ms and 1 every 1s. Press Ctrl+C to stop.")
        last_space = 0.0
        last_one = 0.0

        while True:
            now = time.monotonic()
            if now - last_space >= 0.05:
                send_command(f"KEY,{SPACE_KEY}")
                last_space = now

            if now - last_one >= 1.0:
                send_command("KEY,ONE")
                last_one = now

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
