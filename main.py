import cv2
import numpy as np
import serial
import time
import random
import mss  # Folosim mss pentru a face print screen rapid
import threading

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

def detect_metins():
    """Face screenshot si detecteaza metinele returnand centrele (x, y)."""
    with mss.MSS() as sct:
        # Preluam ecranul principal
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))

        # Scoate canalul alfa (mss returneaza format BGRA)
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
        # Procesare imagine folosind logica data de tine
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Trebuie sa convertim la int32 pentru a preveni overflow la operatii si adunare
        R = img_rgb[:, :, 0].astype(np.int32)
        G = img_rgb[:, :, 1].astype(np.int32)
        B = img_rgb[:, :, 2].astype(np.int32)

        mask = (
            (G >= 80) & (G <= 180) &
            (R >= 5) & (R <= 120) &
            (B >= 3) & (B <= 120) &
            (G > R + 30) &
            (G > B + 30)
        )

        mask = mask.astype(np.uint8) * 255

        # Curatare zgomot (am folosit kernel 3x3 pt metine mici)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        img_height, img_width = img.shape[:2]
        margin = 150  # Ignoram metinele aflate la mai putin de 150px de marginea ecranului

        metin_centers = []
        for cnt in contours:
            area = cv2.contourArea(cnt)

            if area < 100:  # Prag crescut cum ai cerut
                continue

            # Detectie forma circulara
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter ** 2)
            if circularity < 0.5:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            ratio = w / float(h)
            if 0.5 < ratio < 1.5:
                # Calculam centrul casutei
                cx, cy = x + (w // 2), y + (h // 2)
                
                # Excludem metinele care se afla prea aproape de marginile ecranului
                # Pentru ca riscam ca personajul sa aduca click in afara zonei valide sau sa se loveasca de munti / margini
                if cx > margin and cx < (img_width - margin) and cy > margin and cy < (img_height - margin):
                    metin_centers.append((cx, cy))

        return metin_centers, img_height

# Variabila pentru a opri thread-ul secundar elegant
running = True
pause_picking = threading.Event()

def item_picker_worker():
    """Ruleaza independent ca sa apese Z la fiecare ~0.1s indiferent ce face scriptul principal."""
    while running:
        if not pause_picking.is_set():
            # Apasam de 2 ori consecutiv cu mic delay intre ele (hardware are un mic cooldown intern pt HID)
            send_command("KEY,Z")
            time.sleep(0.03)
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
                # Click metine o data la 0.3s + random
                if current_time - last_metin_time >= random_delay(0.3, 0.1):
                    # Acum facem screenshot in timp util si verificam daca se vede un metin
                    metins = detect_metins()
                    
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
                        print(f"[{metins_farmed}/10] Am dat click pe un metin la coord {cx}, {cy}")
                        
                        if metins_farmed == 1:
                            print("Am dat click pe primul metin. Facem pauza de 2 secunde pentru calibrare queue...")
                            time.sleep(random_delay(2.0, 0.5))
                        
                        if metins_farmed >= 6:
                            print("Am atins limita de 10zzz metine. Asteptam cooldown-ul (~1 minut)...")
                            in_cooldown = True
                            
                            # Timp randomizat pentru cooldown in jurul a 60 de secunde
                            cooldown_end_time = current_time + random_delay(30.0, 5.0) 
                            
                    last_metin_time = current_time # Resetam timpul metinului fie ca am gasit sau nu
                    
            # Asteptare mica sa nu incarcam procesorul prea mult
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("Script oprit de utilizator!")
    finally:
        send_command("SHIFT_UP") # Ne asiguram ca e eliberat mereu la inchidere
        ser.close()

if __name__ == "__main__":
