import serial
import time

# schimbi COM3 cu portul tau din Device Manager
ser = serial.Serial("COM7", 115200, timeout=1)
time.sleep(2)  # astepti sa se initializeze

print("Conectat! Testam...")

while True:

    ser.write(b"KEY,Z\n")  # apasa tasta 1
    time.sleep(1)
    
print("Test terminat!")
ser.close()