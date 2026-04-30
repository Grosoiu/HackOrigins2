import cv2
import numpy as np
import serial
import time
import random
import mss  # Folosim mss pentru a face print screen rapid
import threading
import sys
from detector import detect_metins_standard, detect_metins_red

# Configurare port serial
PORT = "COM7"
BAUDRATE = 115200

print(f"Conectare la {PORT}...")
try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=1)
    time.sleep(2)
    print("Conectat cu succes!")
except Exception as e:
    print(f"Eroare la conectare: {e}")
    exit()

# Lock pentru a nu suprapune comenzile pe serial de pe 2 thread-uri diferite
serial_lock = threading.Lock()

def send_command(cmd):
    """Trimite comanda spre microcontroller"""
    with serial_lock:
        ser.write((cmd + "\n").encode())

def random_delay(base_time, variation=0.15):
    """Helper - adauga variatie la timp pentru umanizare (milisecunde adaugate)."""
    return base_time + random.uniform(0.0, variation)

import ctypes

# Structura pentru a citi pozitia mouse-ului nativ de pe Windows
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_mouse_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def move_mouse_hardware(target_x, target_y):
    """Calculeaza diferenta si muta hardware progresiv pentru a atinge coordonata, din cauza acceleratiei de pe Windows"""
    while True:
        curr_x, curr_y = get_mouse_pos()
        dx = target_x - curr_x
        dy = target_y - curr_y
        
        # Daca am ajuns suficient de aproape, ne oprim
        if abs(dx) <= 3 and abs(dy) <= 3:
            break
            
        # Acceleram miscarea, minim 1, maxim 127 pt compatibilitate HID
        step_x = min(max(int(dx * 0.4), -127), 127) 
        step_y = min(max(int(dy * 0.4), -127), 127)
        
        if step_x == 0 and dx != 0: step_x = 1 if dx > 0 else -1
        if step_y == 0 and dy != 0: step_y = 1 if dy > 0 else -1
            
        send_command(f"MOVE,{step_x},{step_y}")
        time.sleep(0.015)  # Pauza mica ca controllerul sa aiba timp sa proceseze

# Variabila pentru a opri thread-ul secundar elegant
running = True
pause_picking = threading.Event()

def item_picker_worker():
    """Ruleaza independent ca sa apese Z continuu, agresiv."""
    while running:
        if not pause_picking.is_set():
            # Apasam de 4 ori consecutiv ca sa ridice itemele picate repede (Fast Pickup rapid)
            send_command("KEY,Z")
            time.sleep(0.015)
            send_command("KEY,Z")
            time.sleep(0.015)
            send_command("KEY,Z")
            time.sleep(0.015)
            send_command("KEY,Z")
        
        # Pauza principala ~0.1s + o mica variatie sa para uman
        time.sleep(random_delay(0.1, 0.05))

def main():
    global running
    print("Incepem automatizarea...")
    
    # Pornim thread-ul pentru ridicat iteme
    picker_thread = threading.Thread(target=item_picker_worker)
    picker_thread.start()
    
    last_metin_time = time.time()
    last_click_time = time.time() # Tine minte cand am lovit cu succes ultima data un metin
    metins_farmed = 0
    in_cooldown = False
    cooldown_end_time = 0
    clicked_metins = [] # memorie pentru a evita click-urile multiple pe acelasi metin

    try:
        while True:
            current_time = time.time()
            
            # 2. Gestionare Metine (Cooldown sau Click)
            if in_cooldown:
                # Asteptam 1 minut dupa 10 metine
                if current_time >= cooldown_end_time:
                    print("Asteptarea a luat sfarsit. Reluam detectia...")
                    in_cooldown = False
                    metins_farmed = 0
                    clicked_metins.clear() # stergem memoria cu metinele anterioare
            else:
                # Verificam daca am inceput un rând de metine dar NU mai gasim alte metine pe ecran
                if metins_farmed > 0 and (current_time - last_click_time) > 4.0:
                    print(f"Am dat click pe {metins_farmed} metine din 6 si nu mai gasesc altele noi! Fortez cooldown-ul.")
                    in_cooldown = True
                    cooldown_end_time = current_time + random_delay(7.0, 2.0)
                    last_click_time = current_time # Resetam ca sa nu intre iara aici
                    continue
                
                # Click metine o data la 0.3s + random
                if current_time - last_metin_time >= random_delay(0.3, 0.1):
                    # Acum facem screenshot in timp util si verificam daca se vede un metin
                    metins, img_height = detect_metins_red()
                    
                    if metins:
                        # Filtram metinele ca sa nu dam click pe unul care e prea aproape de unde am dat deja
                        valid_metins = []
                        for mx, my in metins:
                            too_close = False
                            for cx, cy in clicked_metins:
                                # Daca distanta euclidiana e mai mica de 60 pixeli, spunem ca e fix acelasi metin
                                if (mx - cx)**2 + (my - cy)**2 < 60**2:
                                    too_close = True
                                    break
                            if not too_close:
                                valid_metins.append((mx, my))
                                
                        if not valid_metins:
                            # Toate metinele de pe ecran au fost deja farmate, nu facem nimic
                            last_metin_time = current_time
                            continue
                            
                        # Daca jocul nu duce queue cu alternanta dreapta-stanga / sus-jos (zig-zag prea agresiv),
                        # le ordonam in functie de cat de aproape sunt de ultimul metin pe care am dat click
                        # Astfel personajul se misca fluid intr-o singura directie, curatand ecranul.
                        
                        if len(clicked_metins) > 0:
                            last_click_x, last_click_y = clicked_metins[-1]
                            # Sortam dupa distanta fata de ultimul click, astfel le ia "in lant" (la rand)
                            valid_metins.sort(key=lambda m: (m[0] - last_click_x)**2 + (m[1] - last_click_y)**2)
                            
                            # Alegem urmatorul metin ca fiind strict cel mai apropiat de ultimul metin pe care am dat click
                            # pentru a pastra un lant perfect (fara sa iteram mai mult vizual).
                            target = valid_metins[0]
                        else:
                            # Primul click din serie il dam pur random (sau cu prioritate pe jumatatea vizibila)
                            target = random.choice(valid_metins)
                            
                        cx, cy = target
                        
                        # Salvam pentru a nu mai da click a 2-a oara
                        clicked_metins.append((cx, cy))
                        
                        # Oprim ridicatul de iteme ca sa nu "sparga" Shift + Right Click-ul metinelor in joc
                        pause_picking.set()
                        
                        # Vom simula pe PC miscarea ca apoi sa apasam cu controller-ul
                        move_mouse_hardware(cx, cy)
                        # Pauza ferma sa ne asiguram ca mouse-ul NU se mai misca deloc cand apasa click
                        time.sleep(random_delay(0.15, 0.05)) 
                        
                        # Combinam pe loc: apasam Shift ACUM, dam click scurt, eliberam Shift
                        send_command("SHIFT_DOWN")
                        time.sleep(random_delay(0.05, 0.02)) # Jocul sa citeasca ca Shift-ul e apasat inaine de click
                        
                        send_command("RIGHT_DOWN")
                        time.sleep(random_delay(0.03, 0.02)) # Click extrem de scurt
                        send_command("RIGHT_UP")
                        
                        time.sleep(random_delay(0.03, 0.02))
                        send_command("SHIFT_UP") # Eliberam shift
                        
                        # Start la Z iarasi
                        pause_picking.clear()

                        metins_farmed += 1
                        print(f"[{metins_farmed}/6] Am dat click pe un metin la coord {cx}, {cy}")
                        
                        if metins_farmed == 1:
                            print("Am dat click pe primul metin. Facem pauza de 2 secunde pentru calibrare queue...")
                            time.sleep(random_delay(2.0, 0.5))
                        
                        if metins_farmed >= 6:
                            print("Am atins limita de 6 metine. Asteptam cooldown-ul (~1 minut)...")
                            in_cooldown = True
                            
                            # Timp randomizat pentru cooldown in jurul a 30 de secunde
                            cooldown_end_time = current_time + random_delay(7.0, 2.0) 
                            
                        last_click_time = current_time
                            
                    last_metin_time = current_time # Resetam timpul metinului fie ca am gasit sau nu
                    
            # Asteptare mica sa nu incarcam procesorul prea mult
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("Script oprit de utilizator!")
    finally:
        send_command("SHIFT_UP") # Ne asiguram ca e eliberat mereu la inchidere
        ser.close()

if __name__ == "__main__":
    main()
