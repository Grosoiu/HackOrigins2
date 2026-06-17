import cv2
import numpy as np
import serial
import time
import random
import mss  # Folosim mss pentru a face print screen rapid
import threading
import sys
import subprocess
from detector import detect_metins_standard, detect_metins_red, detect_metins_shape, detect_metins_ice, detect_fireland_metins, detect_fish_obs, detect_mines
from detect_pm.pm_detector import detect_pm_flag
from detect_pm.telegram_notify import send_telegram_message

# Configurare port serial
PORT = "COM3"
BAUDRATE = 115200
PM_CHECK_INTERVAL = 1.0
PM_THRESHOLD = 0.9

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
import win32gui

# Structura pentru a citi pozitia mouse-ului nativ de pe Windows
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_mouse_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def get_game_offset():
    """Afla coordonata absoluta (x,y) de pe desktop a colțului ferestrei jocului."""
    hwnd = win32gui.FindWindow(None, "Origins")
    if hwnd:
        pt = POINT(0, 0) # Colțul top-left al zonei de randare a jocului (fara Windows bar)
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
        return pt.x, pt.y
    return 0, 0

def move_mouse_hardware(target_x, target_y, is_fishing=False, force=False):
    """Calculeaza diferenta si muta hardware progresiv pentru a atinge coordonata, din cauza acceleratiei de pe Windows"""
    if is_fishing:
        curr_x, curr_y = get_mouse_pos()
        dx = target_x - curr_x
        dy = target_y - curr_y
        
        while dx != 0 or dy != 0:
            if not force and stop_event.is_set():
                break
            step_x = min(max(dx, -127), 127)
            step_y = min(max(dy, -127), 127)
            send_command(f"MOVE,{step_x},{step_y}")
            dx -= step_x
            dy -= step_y
            time.sleep(0.001)
        return

    while True:
        if not force and stop_event.is_set():
            break
        curr_x, curr_y = get_mouse_pos()
        dx = target_x - curr_x
        dy = target_y - curr_y
        
        threshold = 5 if is_fishing else 3
        if abs(dx) <= threshold and abs(dy) <= threshold:
            break
            
        multiplier = 0.85 if is_fishing else 0.4
        step_x = min(max(int(dx * multiplier), -127), 127) 
        step_y = min(max(int(dy * multiplier), -127), 127)
        
        if step_x == 0 and dx != 0: step_x = 1 if dx > 0 else -1
        if step_y == 0 and dy != 0: step_y = 1 if dy > 0 else -1
            
        send_command(f"MOVE,{step_x},{step_y}")
        
        sleep_t = 0.005 if is_fishing else 0.015
        time.sleep(sleep_t)

# Variabila pentru a opri thread-ul secundar elegant
running = True
pause_picking = threading.Event()
stop_event = threading.Event()
pm_match_center = None  # Coordonatele PM-ului detectat, setat de pm_monitor_worker

# Mapare caractere speciale catre comenzi HID
_SPECIAL_KEYS = {
    " ": "SPACE",
    "!": "SHIFT_EXCL",  # Shift + 1 – trimitem manual mai jos
}

# Caractere care necesita Shift
_SHIFT_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+{}|:\"<>?")

def type_string_hardware(text: str, char_delay: float = 0.06):
    """Trimite un text complet prin HID, caracter cu caracter.
    Folosim KEY_DOWN + delay + KEY_UP ca jocul sa inregistreze fiecare tasta."""
    for ch in text:
        if ch == " ":
            send_command("KEY_DOWN,SPACE")
            time.sleep(0.03)
            send_command("KEY_UP,SPACE")
        elif ch == "!":
            send_command("SHIFT_DOWN")
            time.sleep(0.03)
            send_command("KEY_DOWN,ONE")
            time.sleep(0.03)
            send_command("KEY_UP,ONE")
            time.sleep(0.02)
            send_command("SHIFT_UP")
        elif ch.isalpha() and ch.isupper():
            send_command("SHIFT_DOWN")
            time.sleep(0.03)
            send_command(f"KEY_DOWN,{ch.upper()}")
            time.sleep(0.03)
            send_command(f"KEY_UP,{ch.upper()}")
            time.sleep(0.02)
            send_command("SHIFT_UP")
        elif ch.isalpha():
            send_command(f"KEY_DOWN,{ch.upper()}")
            time.sleep(0.03)
            send_command(f"KEY_UP,{ch.upper()}")
        else:
            # Skip unhandled characters
            pass
        time.sleep(char_delay)

def handle_pm_response(match_center):
    """
    Raspunde automat la PM-ul detectat:
    1. Pauza 1s dupa oprirea automatizarii (sa se opreasca totul)
    2. 3x click pe icoana PM cu 300ms intre ele
    3. Click la 300x380 (camp de text)
    4. Scrie "Yes going to sleep!"
    5. Trimite mesajul (Enter)
    6. Inchide procesul Origins
    """
    if match_center is None:
        print("[PM] Nu am coordonate de match, sar peste raspuns automat.")
        return

    mx, my = match_center

    # Asteptam 1 secunda ca totul sa se opreasca (metine, pickup, etc.)
    print("[PM] Eliberam tastele si asteptam 1 secunda...")
    send_command("SHIFT_UP")
    send_command("RIGHT_UP")
    send_command("LEFT_UP")
    time.sleep(1.0)

    # Mutam mouse-ul pe icoana PM
    print(f"[PM] Mutam mouse-ul pe PM la ({mx}, {my})...")
    move_mouse_hardware(mx, my, is_fishing=False, force=True)
    time.sleep(0.3)

    # 3 click-uri pe icoana PM cu 300ms delay intre ele
    for i in range(3):
        send_command("LEFT_DOWN")
        time.sleep(0.04)
        send_command("LEFT_UP")
        print(f"[PM] Click {i+1}/3 pe PM")
        time.sleep(0.3)

    # Asteptam sa se deschida fereastra PM
    time.sleep(1.0)

    # Click la 300x380 (campul de input / raspuns)
    print("[PM] Click la (300, 380) pentru campul de text...")
    move_mouse_hardware(300, 380, is_fishing=False, force=True)
    time.sleep(0.3)
    send_command("LEFT_DOWN")
    time.sleep(0.04)
    send_command("LEFT_UP")
    time.sleep(0.4)

    # Scriem mesajul
    reply_text = "Hi, yes, will be going to sleep soon! Thanks for the PM :)"
    print(f"[PM] Scriem: \"{reply_text}\"")
    type_string_hardware(reply_text)
    time.sleep(0.3)

    # Trimitem mesajul cu Enter
    send_command("KEY_DOWN,ENTER")
    time.sleep(0.05)
    send_command("KEY_UP,ENTER")
    time.sleep(0.5)

    # Inchidem procesul Origins (cautam dupa titlul ferestrei)
    print("[PM] Inchidem procesul Origins...")
    try:
        hwnd = win32gui.FindWindow(None, "Origins")
        if hwnd:
            # Obtinem PID-ul din window handle
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            subprocess.run(["taskkill", "/f", "/pid", str(pid.value)], timeout=5)
            print(f"[PM] Origins (PID {pid.value}) inchis cu succes.")
        else:
            print("[PM] Nu am gasit fereastra Origins.")
    except Exception as e:
        print(f"[PM] Eroare la inchiderea Origins: {e}")

def item_picker_worker():
    """Ruleaza independent ca sa apese Z continuu, agresiv."""
    while running and not stop_event.is_set():
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

def pm_monitor_worker(interval=PM_CHECK_INTERVAL, threshold=PM_THRESHOLD):
    global running, pm_match_center
    while not stop_event.is_set():
        try:
            flag, score, match_center = detect_pm_flag(debug=True, threshold=threshold)
        except Exception as e:
            print(f"[PM] Eroare detectie: {e}")
            time.sleep(interval)
            continue

        if flag:
            print(f"[PM] PM detectat. Score={score:.3f}. Oprim automatizarea.")
            msg = f"PM detectat in joc. Score={score:.3f}."
            if not send_telegram_message(msg, debug=True):
                print("[PM] Nu am putut trimite mesaj Telegram (token/chat_id lipsa sau eroare).")
            pm_match_center = match_center
            stop_event.set()
            running = False
            pause_picking.set()
            break

        time.sleep(interval)

def fishing_loop():
    global running
    print("\nPregatim camera virtuala de la OBS (index 1)...")
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    
    # Dimensiunea ecranului setata in prealabil (pentru centru calibrat perfect pe 1366x768)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1366)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 768)
    
    if not cap.isOpened():
        print("Eroare la deschiderea OBS Virtual Camera. Verifica daca ai pornit-o din OBS!")
        return

    print("Incepem Pescuitul Automatizat în 5 secunde! Plaseaza ferestrele corect.")
    time.sleep(5)
    
    try:
        in_minigame = False
        last_fish_time = time.time()
        last_action_time = time.time() # Failsafe absolut pentru blocaje
        
        while not stop_event.is_set():
            start_time = time.time()
            
            fish_pos, minigame_active = detect_fish_obs(cap)
            
            if minigame_active:
                in_minigame = True
                last_fish_time = time.time()
                last_action_time = time.time()
                
            if fish_pos:
                fx, fy = fish_pos
                
                # Transformam coordonata OBS intr-o coordonata REALĂ de pe ecran
                offset_x, offset_y = get_game_offset()
                real_fx = fx + offset_x
                real_fy = fy + offset_y
                
                # Diferența catre Arduino este Relativă fața de cursorul de pe Windows
                move_mouse_hardware(real_fx, real_fy, is_fishing=True)
                
                time.sleep(0.02)  # O mică pauză ca jocul să actualizeze poziția de hover
                
                send_command("LEFT_DOWN")
                time.sleep(0.05) # Tinem apasat puțin mai mult ca să înregistreze Metin2 (50ms)
                send_command("LEFT_UP")
                
                print(f"Click la ({real_fx}, {real_fy})")
                
                # Pauza intre click-uri redusa DRASTIC la ~0.15 secunde
                time.sleep(random_delay(0.15, 0.05)) 
            else:
                current_time = time.time()
                # 1. Daca minigame-ul s-a terminat normal (nu am vazut pestele 2.5s)
                timeout_normal_ms = in_minigame and (current_time - last_fish_time) > 2.5
                # 2. Daca a luat complet razna / fail / n-a gasit deloc si s-a blocat in asteptare (> 8s)
                timeout_absolute_failsafe = not in_minigame and (current_time - last_action_time) > 8.0
                
                if timeout_normal_ms or timeout_absolute_failsafe:
                    if timeout_absolute_failsafe:
                        print("FAILSAFE Pescuit depasit 35s. Timpul a expirat! Repornesc pescuitul...")
                    else:
                        print("Minigame-ul s-a incheiat normal (pestele a disparut).")
                    
                    time.sleep(random_delay(2.0, 0.5))
                    
                    print("Punem rama (Apasam tasta 4)")
                    send_command("KEY,FOUR")
                    time.sleep(random_delay(1.5, 0.3))
                    
                    print("Aruncam undita (Apasam tasta SPACE)")
                    send_command("KEY,SPACEBAR")
                    send_command("KEY,SPACE")
                    
                    in_minigame = False
                    last_fish_time = current_time
                    last_action_time = current_time
                    print("Incepem sa cautam pesti imediat!")
            
            elapsed = time.time() - start_time
            # Procesare ultra-rapida (aprox 100 FPS cap)
            sleep_time = max(0.01 - elapsed, 0)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("Pescuit oprit de utilizator!")
    finally:
        cap.release()
        send_command("LEFT_UP")
        send_command("SHIFT_UP")

def mining_loop():
    global running
    print("\nIncepem Mineritul Automatizat în 5 secunde!...")
    time.sleep(5)
    
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        center_x = monitor["width"] // 2
        center_y = monitor["height"] // 2

    try:
        while not stop_event.is_set():
            mines, img_height = detect_mines()
            
            if mines:
                # Sortam si prioritizam zacamantul cel mai aproape de personaj (centrul ecranului)
                mines.sort(key=lambda m: (m[0] - center_x)**2 + (m[1] - center_y)**2)
                target = mines[0]
                cx, cy = target
                
                move_mouse_hardware(cx, cy, is_fishing=False)
                time.sleep(random_delay(0.15, 0.05))
                
                # Click stanga pe zacamant
                send_command("LEFT_DOWN")
                time.sleep(random_delay(0.05, 0.02))
                send_command("LEFT_UP")
                
                print(f"Am dat click pe zacamant la {cx}, {cy}. Asteptam 15 secunde si ridicam iteme...")
                
                # Asteptam ~15 secunde (timpul de actiune la minat) inainte de a da alt click.
                # Apasam 'Z' in timp ce minam in caz cazz mai cade ceva sau la final.zzzzzzzz
                for i in range(3):
                    send_command("KEY,Z")
                    time.sleep(0.3)
                    
            else:
                # Niciun zacamant vizibil, mai cautam scurt
                time.sleep(0.5)

    except KeyboardInterrupt:
        print("Minerit oprit de utilizator!")
    finally:
        send_command("LEFT_UP")
        send_command("SHIFT_UP")

def main():
    global running
    
    pick_items_input = input("Vrei sa fie activa functia de ridicat iteme (Z)? (da/nu): ").strip().lower()
    pick_items = pick_items_input in ['da', 'd', 'yes', 'y', '1']
    
    print("\nAlege metoda de actiune:")
    print("1. Standard (Farmare Metine)")
    print("2. Rosu (Farmare Metine Rosii)")
    print("3. Shape (Metine cu contur/template)")
    print("7. Gheata (Farmare Metine de Gheata)")
    print("6. Fireland (Farmare Metine Violet)")
    print("z. Pescuit (Folosind OBS Virtual Camera)")
    print("5. Minerit (Farmare Zacaminte)")
    method_input = input("Introdu numarul (1/2/3/4/5/6/7): ").strip()

    pm_thread = threading.Thread(target=pm_monitor_worker, daemon=True)
    pm_thread.start()
    
    if method_input == '5':
        print("Ai ales modul: Minerit")
        # Nu pornim thread-ul de pick agresiv, facem pickup manual in loop in ritm de 1s
        mining_loop()
        ser.close()
        return

    if method_input == '4':
        print("Ai ales modul: Pescuit")
        if pick_items:
            picker_thread = threading.Thread(target=item_picker_worker)
            picker_thread.start()
        fishing_loop()
        ser.close()
        return

    fireland_mode = False
    if method_input == '2':
        detect_func = detect_metins_red
        print("Ai ales detectarea metinelor: Rosu")
    elif method_input == '3':
        detect_func = detect_metins_shape
        print("Ai ales detectarea metinelor: Shape")
    elif method_input == '7':
        detect_func = detect_metins_ice
        print("Ai ales detectarea metinelor: Gheata")
    elif method_input == '6':
        detect_func = detect_fireland_metins
        fireland_mode = True
        print("Ai ales detectarea metinelor: Fireland")
    else:
        detect_func = detect_metins_standard
        print("Ai ales detectarea metinelor: Standard")
        
    print("\nIncepem automatizarea...")
    time.sleep(5)
    
    # Pornim thread-ul pentru ridicat iteme doar daca s-a ales
    if pick_items:
        picker_thread = threading.Thread(target=item_picker_worker)
        picker_thread.start()
        print("Functia de ridicat iteme (Z) este ACTIVA.")
    else:
        print("Functia de ridicat iteme (Z) este INACTIVA.")
    
    last_metin_time = time.time()
    last_click_time = time.time() # Tine minte cand am lovit cu succes ultima data un metin
    metins_farmed = 0
    in_cooldown = False
    cooldown_end_time = 0
    clicked_metins = [] # memorie pentru a evita click-urile multiple pe acelasi metin

    try:
        while not stop_event.is_set():
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
                    result = detect_func(show_result=False) if fireland_mode else detect_func()
                    metins = result[0]
                    
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
                        # Astfel personajul se misca fluid intr-o singura directie, curatind ecranul.
                        
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
                        move_mouse_hardware(cx, cy, is_fishing=False)
                        # Pauza ferma sa ne asiguram ca mouse-ul NU se mai misca deloc cand apasa click
                        time.sleep(random_delay(0.15, 0.05)) 
                        
                        # Combinam pe loc: apasam Shift ACUM, dam click scurt, eliberam Shift
                        send_command("SHIFT_DOWN")
                        time.sleep(random_delay(0.05, 0.02)) # Jocul sa citeasca ca Shift-ul e apasat inaine de click
                        
                        send_command("RIGHT_DOWN")
                        time.sleep(random_delay(0.02, 0.02)) # Click extrem de scurt
                        send_command("RIGHT_UP")

                        send_command("RIGHT_DOWN")
                        time.sleep(random_delay(0.02, 0.02)) # Click extrem de scurt
                        send_command("RIGHT_UP")
                        
                        time.sleep(random_delay(0.03, 0.02))
                        send_command("SHIFT_UP") # Eliberam shift
                        
                        # Start la Z iarasi
                        pause_picking.clear()

                        metins_farmed += 1
                        print(f"[{metins_farmed}/6] Am dat click pe un metin la coord {cx}, {cy}")
                        
                        if metins_farmed == 1:
                            print("Am dat click pe primul metin. Facem pauza de 2 secunde pentru calibrare queue...")
                            time.sleep(random_delay(1.0, 0.5))
                        
                        if metins_farmed >= 10:
                            print("Am atins limita de 10 metine. Asteptam cooldown-ul (~1 minut)...")
                            in_cooldown = True
                            
                            # Timp randomizat pentru cooldown in jurul a 30 de secunde
                            cooldown_end_time = current_time + random_delay(4.0, 1.0) 
                            
                        last_click_time = current_time
                            
                    last_metin_time = current_time # Resetam timpul metinului fie ca am gasit sau nu
                    
            # Asteptare mica sa nu incarcam procesorul prea mult
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("Script oprit de utilizator!")
    finally:
        send_command("SHIFT_UP") # Ne asiguram ca e eliberat mereu la inchidere

        # Daca PM-ul a oprit automatizarea, raspundem din thread-ul principal (fara conflicte serial)
        if pm_match_center is not None:
            print("[PM] Automatizarea s-a oprit. Raspundem la PM din thread-ul principal...")
            handle_pm_response(pm_match_center)

        ser.close()

if __name__ == "__main__":
    main()