import cv2
import numpy as np
import mss

def detect_metins_standard(margin=60):
    """Face screenshot si detecteaza metinele returnand centrele (x, y) si inaltimea imaginii."""
    with mss.MSS() as sct:
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
    with mss.MSS() as sct:
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
