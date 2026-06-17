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

def detect_metins_ice(margin=60, debug=False, image_bgr=None):
    """
    Detecteaza metinele de gheata.
    Returneaza:
        - lista centre [(x, y)]
        - imaginea cu overlay (optional)
        - masca (optional)
    Daca image_bgr este furnizata, nu mai face screenshot.
        # ---------------------------------------------------------------------------
        # Zone de UI ignorate (layout 1920x1080, full-screen). Ajusteaza la rezolutia ta.
        # Format: (x0, y0, x1, y1)
        # ---------------------------------------------------------------------------
    """

    with mss.mss() as sct:

        if image_bgr is None:
            monitor = sct.monitors[1]
            img_bgr = np.array(sct.grab(monitor))
        else:
            img_bgr = image_bgr

        if img_bgr is None:
            raise ValueError("Nu am primit o imagine valida pentru detectie.")

        # Normalizeaza formatul in BGR
        if img_bgr.ndim == 2:
            img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGR)
        elif img_bgr.shape[2] == 4:
            img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # =========================================================
        # RGB channels
        # =========================================================
        R = img_rgb[:, :, 0].astype(np.int32)
        G = img_rgb[:, :, 1].astype(np.int32)
        B = img_rgb[:, :, 2].astype(np.int32)

        # =========================================================
        # MASCA METINE
        # calibrata pe:
        # RGB 164 190 213
        # RGB 144 165 189
        # =========================================================

        mask = (
            (R >= 120) & (R <= 190) &
            (G >= 140) & (G <= 210) &
            (B >= 160) & (B <= 240) &

            # metinele sunt mai albastre
            ((B - R) >= 15) &
            ((B - G) >= 5) &

            # eliminare podea
            ((G - R) <= 45)
        )

        mask = mask.astype(np.uint8) * 255

        # =========================================================
        # MORPHOLOGY
        # facem clusterele mai mari
        # =========================================================

        kernel_open = np.ones((3, 3), np.uint8)
        kernel_dilate = np.ones((9, 9), np.uint8)

        # elimina zgomot mic
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)

        # uneste componentele metinului
        mask = cv2.dilate(mask, kernel_dilate, iterations=2)

        # smooth
        mask = cv2.GaussianBlur(mask, (7, 7), 0)

        # threshold din nou dupa blur
        _, mask = cv2.threshold(mask, 80, 255, cv2.THRESH_BINARY)

        # =========================================================
        # CONTOURS
        # =========================================================

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        result = img_rgb.copy()

        img_h, img_w = img_rgb.shape[:2]

        metin_centers = []

        for cnt in contours:

            area = cv2.contourArea(cnt)

            # filtre bune pentru imaginea asta
            if area < 700:
                continue

            if area > 12000:
                continue

            perimeter = cv2.arcLength(cnt, True)

            if perimeter == 0:
                continue

            circularity = 4 * np.pi * area / (perimeter * perimeter)

            # metinele sunt compacte
            if circularity < 0.20:
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            ratio = w / float(h)

            # forma aproximativ patrata
            if not (0.45 <= ratio <= 1.8):
                continue

            cx = x + w // 2
            cy = y + h // 2

            # evita marginile
            if (
                cx < margin or
                cx > img_w - margin or
                cy < margin or
                cy > img_h - margin
            ):
                continue

            metin_centers.append((cx, cy))

            # =====================================================
            # DRAW
            # =====================================================

            cv2.drawContours(result, [cnt], -1, (0, 255, 0), 2)

            cv2.circle(
                result,
                (cx, cy),
                6,
                (255, 0, 0),
                -1
            )

            cv2.putText(
                result,
                f"{cx},{cy}",
                (cx + 10, cy),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

        # =========================================================
        # DEBUG
        # =========================================================

        if debug:

            cv2.imshow("mask", mask)
            cv2.imshow(
                "result",
                cv2.cvtColor(result, cv2.COLOR_RGB2BGR)
            )

            cv2.waitKey(0)
            cv2.destroyAllWindows()


        return metin_centers, result, mask

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


# ---------------------------------------------------------------------------
# Zone de UI ignorate (layout 1920x1080, full-screen). Ajusteaza la rezolutia ta.
# Format: (x0, y0, x1, y1)
# ---------------------------------------------------------------------------
UI_ZONES_1080 = [
    (0,    0,   405, 108),    # bara de iconite stanga-sus
    (1555, 0,  1920, 250),    # minimap + panou eveniment (dreapta-sus)
    (900,  0,   985, 60),     # iconita cos / shop (centru-sus)
    (0,    968, 1920, 1080),  # chat + bara de skilluri (jos)
    (0,    785, 260, 875),    # panoul de status (stanga-jos)
    (760,  395, 1045, 670),   # personaj + pet + gramada de mobi (centrul ecranului)
]


def _relief(gray):
    """Deviatia standard locala a luminantei = energia de relief (textura 3D)."""
    k = 15
    m = cv2.boxFilter(gray, -1, (k, k))
    s = cv2.boxFilter(gray * gray, -1, (k, k))
    return np.sqrt(np.maximum(s - m * m, 0)) > 21


def _terrain_mass(relief, min_mass=25000):
    """Mase mari, continue de relief = munte / pod / padure / gramada de mobi."""
    H, W = relief.shape
    closed = cv2.morphologyEx(
        relief.astype(np.uint8) * 255, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(closed, 8)
    terr = np.zeros((H, W), np.uint8)
    for i in range(1, n):
        if st[i, 4] > min_mass:
            terr[lab == i] = 255
    return terr > 0


def _build_metin_mask(img_bgr, ui_zones):
    H, W = img_bgr.shape[:2]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    Hh = hsv[:, :, 0].astype(np.int32)
    Ss = hsv[:, :, 1].astype(np.int32)
    B = img_bgr[:, :, 0].astype(np.int32)
    G = img_bgr[:, :, 1].astype(np.int32)
    R = img_bgr[:, :, 2].astype(np.int32)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)

    relief = _relief(gray)
    blue  = (B > R + 10) & (Ss >= 28)                                       # Gheata
    green = (Hh >= 42) & (Hh <= 92) & (G > R + 8) & (G > B + 8) & (Ss >= 50) # Vant
    red   = (Hh <= 16) & (Ss >= 78) & (R > G + 25) & (R > B + 45)            # Pamant rosu
    cand = relief | blue | green | red

    ui = np.zeros((H, W), dtype=bool)
    for (x0, y0, x1, y1) in ui_zones:
        ui[y0:y1, x0:x1] = True
    cand &= ~ui

    mask = cand.astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    # Umplem interiorul fiecarui metin PE COMPONENTA (sigur), nu cu flood-fill
    # global din colt - acela se umfla la tot ecranul cand un zid/cladire/UI
    # inconjoara campul.
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, cnts, -1, 255, -1)
    mask = filled
    mask = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    return mask, relief


def _on_open_ground(hsv, blob):
    """
    Testeaza daca obiectul sta pe terenul farmabil (iarba/piatra calda) si nu
    pe munte/padure. Verifica culoarea medie a inelului din jurul obiectului:
      - teren bun  -> ton cald (H 15-42), saturatie medie (S 34-78), luminos (V>=82)
      - munte/stanca -> gri desaturat (S mic) ; padure -> verde (H mare)
    """
    inner = cv2.dilate(blob, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    outer = cv2.dilate(blob, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (45, 45)))
    ring = cv2.subtract(outer, inner) > 0
    if ring.sum() < 50:
        return False
    h = np.median(hsv[ring][:, 0]); s = np.median(hsv[ring][:, 1]); v = np.median(hsv[ring][:, 2])
    return (15 <= h <= 42) and (34 <= s <= 78) and (v >= 82)


def detect_metins_relief(margin=55, ui_zones=None, min_area=650, max_area=20000):
    """
    Face screenshot si detecteaza metinele (Gheata / Vant / Pamant / Foc) pe
    terenul farmabil, ignorand muntele, podul, padurea si gramada de mobi.
    Returneaza (metin_centers, img_height) - aceeasi semnatura ca celelalte functii.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        if ui_zones is None:
            ui_zones = UI_ZONES_1080

        H, W = img.shape[:2]
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask, relief = _build_metin_mask(img, ui_zones)
        terrain = _terrain_mass(relief)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        metin_centers = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:    # prea mic / mase uriase (munte, pod)
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if h < 20 or max(w, h) < 36:
                continue

            blob = np.zeros((H, W), np.uint8)
            cv2.drawContours(blob, [cnt], -1, 255, -1)
            bpx = blob > 0

            # respinge ce se suprapune cu o masa mare de teren (munte/pod/mobi)
            if float(terrain[bpx].mean()) > 0.30:
                continue
            # pastreaza doar ce sta pe terenul farmabil
            if not _on_open_ground(hsv, blob):
                continue

            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"]); cy = int(M["m01"] / M["m00"])
            if margin < cx < W - margin and margin < cy < H - margin:
                metin_centers.append((cx, cy))

        return metin_centers, H


def detect_metins_shape(margin=55, ui_zones=None):
    """Compat wrapper: foloseste detectia pe relief in loc de template matching."""
    return detect_metins_relief(margin=margin, ui_zones=ui_zones)

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
        
    width, height = 1920, 1080
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
