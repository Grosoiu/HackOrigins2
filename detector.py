import cv2
import numpy as np
import mss

def detect_metins_standard(margin=60):
    """Face screenshot si detecteaza metinele returnand centrele (x, y) si inaltimea imaginii."""
    with mss.mss() as sct:
        # Preluam ecranul principal
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))

        # Scoate canalul alfa (mss returneaza format BGRA)
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
        # Procesare imagine folosind logica
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

def detect_metins_red(margin=60):
    """Face screenshot si detecteaza metinele rosii returnand centrele (x, y) si inaltimea imaginii."""
    with mss.mss() as sct:
        # Preluam ecranul principal
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))

        # Scoate canalul alfa (mss returneaza format BGRA)
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
        # Procesare imagine
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Convertim la int32 pentru a preveni overflow la calcule
        R = img_rgb[:, :, 0].astype(np.int32)
        G = img_rgb[:, :, 1].astype(np.int32)
        B = img_rgb[:, :, 2].astype(np.int32)

        # mask pentru metine roșii
        mask = (
            (R > 120) &
            (G > 60) & (G < 150) &
            (B < 120) &
            (R > G + 20) &
            (R > B + 40)
        )

        mask = mask.astype(np.uint8) * 255

        # curățare - kernel de 5x5 conform codului dat
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        img_height, img_width = img.shape[:2]

        metin_centers = []
        for cnt in contours:
            area = cv2.contourArea(cnt)

            # elimină text + UI conform noului prag
            if area < 80 or area > 2000:
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # metinele sunt relativ compacte
            ratio = w / float(h)
            if 0.6 < ratio < 1.4:
                # Calculam centrul casutei
                cx, cy = x + (w // 2), y + (h // 2)
                
                # Excludem metinele care se afla prea aproape de marginile ecranului
                if cx > margin and cx < (img_width - margin) and cy > margin and cy < (img_height - margin):
                    metin_centers.append((cx, cy))

        return metin_centers, img_height

def detect_metins_snake(margin_pct=0.2, y_offset=50):
    """
    Face screenshot si detecteaza metinele cautand textul lor alb (Snake), 
    returnand centrele modificate in jos (pt a lovi metinul) si inaltimea imaginii.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))

        # Scoatem canalul alfa
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
        height, width = img.shape[:2]

        # 1. Margini - cautam doar in mijloc pt a evita chat, nume playeri, etc
        margin_y = int(height * margin_pct)
        margin_x = int(width * margin_pct)
        
        roi_mask = np.zeros((height, width), dtype=np.uint8)
        roi_mask[margin_y:height-margin_y, margin_x:width-margin_x] = 255

        # 2. Detectie culoare alb curat
        # img in OpenCV este BGR, asa ca formatul este [B, G, R]
        lower_white = np.array([245, 245, 245], dtype=np.uint8)
        upper_white = np.array([255, 255, 255], dtype=np.uint8)
        
        color_mask = cv2.inRange(img, lower_white, upper_white)

        # 3. Masca finala care pastreaza doar centrul
        final_mask = cv2.bitwise_and(color_mask, roi_mask)

        # 4. Clean-up morofologic ca in test (doar dilatare cu kernel text)
        kernel_text = np.ones((2, 10), np.uint8)
        clean_mask = cv2.dilate(final_mask, kernel_text, iterations=1)

        contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        metin_centers = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Filtram forma specifică de text alb mic returnată de algoritm
            if area > 10 and w > 10 and h >= 3 and w > h:
                # Calculam centrul textului determinat
                cx = x + (w // 2)
                # Adaugam cativa pixeli in jos (ex. y_offset) pentru a indica corpul metinului, nu textul
                cy = y + (h // 2) + y_offset
                
                metin_centers.append((cx, cy))

        return metin_centers, height

def detect_fireland_metins(margin=60, show_result=True):
    """
    Detecteaza metinele violet din Fireland si afiseaza masca + detectiile.

    Returneaza:
        metin_centers -> lista de tuple (x, y)
        mask -> imaginea binara folosita la detectie
        result -> imaginea finala cu detectiile desenate
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))

    # Convertim BGRA -> BGR
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    original = img.copy()

    # RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    R = img_rgb[:, :, 0].astype(np.int32)
    G = img_rgb[:, :, 1].astype(np.int32)
    B = img_rgb[:, :, 2].astype(np.int32)

    """
    Fireland metins:
    - violet / mov
    - B si R dominante
    - G mai mic
    """

    mask = (
        (R > 55) &
        (B > 55) &
        (G < 90) &
        (R < 190) &
        (B < 190) &
        # mov = R si B apropiate
        (np.abs(R - B) < 70) &
        # mov dominant peste verde
        (R > G + 25) &
        (B > G + 25)
    )

    # uint8
    mask = mask.astype(np.uint8) * 255

    # Curatare zgomot
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.dilate(mask, kernel, iterations=1)

    # Contours
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    img_height, img_width = img.shape[:2]

    metin_centers = []

    for cnt in contours:
        area = cv2.contourArea(cnt)

        # filtre bune pentru metine Fireland
        if area < 60 or area > 2500:
            continue

        perimeter = cv2.arcLength(cnt, True)

        if perimeter == 0:
            continue

        circularity = 4 * np.pi * area / (perimeter ** 2)

        # metinele sunt compacte
        if circularity < 0.35:
            continue

        x, y, w, h = cv2.boundingRect(cnt)

        ratio = w / float(h)

        # aproximativ patrate
        if not (0.5 < ratio < 1.5):
            continue

        cx = x + w // 2
        cy = y + h // 2

        # evita marginile
        if (
            cx < margin or
            cx > img_width - margin or
            cy < margin or
            cy > img_height - margin
        ):
            continue

        metin_centers.append((cx, cy))

        # Draw detection
        cv2.rectangle(original, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.circle(original, (cx, cy), 4, (0, 0, 255), -1)

    # Overlay masca peste imagine
    colored_mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    overlay = original.copy()
    overlay[:, :, 1] = np.maximum(overlay[:, :, 1], mask)

    if show_result:
        cv2.imshow("MASK", mask)
        cv2.imshow("RESULT", overlay)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return metin_centers, mask, overlay

def detect_fish_obs(cap):
    """
    Face o citire rapida direct din fluxul VideoCapture (OBS Virtual Camera).
    Returneaza 2 variabile: 
    1. (x, y) - Daca pestele este in cercul interior (< 58px) unde avem voie sa dam click
    2. True/False - Daca pestele a fost detectat oriunde in aria mare a minigame-ului (pentru a sti ca minigame-ul exista)
    """
    ret, frame = cap.read()
    if not ret:
        return None, False
        
    width, height = 1366, 768
    center_x, center_y = width // 2, height // 2

    # Toleranta pt culoarea pestelui
    lower_color = np.array([115, 85, 55], dtype=np.uint8)
    upper_color = np.array([125, 95, 65], dtype=np.uint8)

    # Cream o masca mare cat fereastra de minigame (~150px) ca sa vedem daca exista pestele
    mask_large = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.circle(mask_large, (center_x, center_y), 150, 255, -1)

    circle_roi = cv2.bitwise_and(frame, frame, mask=mask_large)
    color_mask = cv2.inRange(circle_roi, lower_color, upper_color)

    contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    is_minigame_active = False
    valid_click_pos = None

    for cnt in contours:
        if cv2.contourArea(cnt) > 5:
            is_minigame_active = True
            
            x, y, w, h = cv2.boundingRect(cnt)
            cx, cy = x + (w // 2), y + (h // 2)
            
            dist_to_center = ((cx - center_x)**2 + (cy - center_y)**2)**0.5
            if dist_to_center <= 58:
                valid_click_pos = (cx, cy)
            
            break 
            
    return valid_click_pos, is_minigame_active

def detect_mines(margin=60, y_offset=15):
    """Face screenshot si detecteaza zacamintele returnand centrele (x, y) modificate in jos pentru a face click pe ele."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))

        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # convertim culoarea target în HSV
        target_bgr = np.uint8([[[93, 231, 121]]])
        target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0][0]

        # toleranta (am marit plaja pentru a prinde nuantele textului mai bine)
        lower = np.array([max(0, target_hsv[0]-3), 50, 50])
        upper = np.array([min(179, target_hsv[0]+3), 255, 255])

        mask = cv2.inRange(hsv, lower, upper)

        # unire text cu un kernel lat pentru a prinde conturul intregului text
        kernel_text = np.ones((5, 20), np.uint8)
        mask = cv2.dilate(mask, kernel_text, iterations=1)

        # gasim contururi
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        img_height, img_width = img.shape[:2]

        mine_centers = []
        for cnt in contours:
            x,y,w,h = cv2.boundingRect(cnt)
            
            # cerem si ca lungimea textului sa fie vizibil mai mare decat inaltimea sa
            if w*h > 50 and w > h * 3.7:
                cx = x + w//2
                cy = y + h//2 + y_offset
                
                if cx > margin and cx < (img_width - margin) and cy > margin and cy < (img_height - margin):
                    mine_centers.append((cx, cy))

        return mine_centers, img_height
