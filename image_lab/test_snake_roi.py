import cv2
import numpy as np
import os

def test_snake_roi():
    # Asigura-te ca rulezi scriptul din folderul in care se afla si imaginea (image_lab)
    img_path = "img.png"
    if not os.path.exists(img_path):
        print(f"Fisierul {img_path} nu a fost gasit.")
        return

    img = cv2.imread(img_path)
    height, width = img.shape[:2]

    # Detectie text alb curat
    lower_white = np.array([245, 245, 245], dtype=np.uint8)
    upper_white = np.array([255, 255, 255], dtype=np.uint8)
    
    color_mask = cv2.inRange(img, lower_white, upper_white)

    # Clean-up pe masca textului
    kernel_text = np.ones((2, 10), np.uint8)
    clean_mask = cv2.dilate(color_mask, kernel_text, iterations=1)

    contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    output_img = img.copy()
    
    # Cream o imagine neagra pe care vom randa muchiile gasite prin Canny (masca)
    debug_mask = np.zeros((height, width), dtype=np.uint8)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        x, y, w, h = cv2.boundingRect(cnt)
        
        # Filtrul pentru dimensiunea textului
        if area > 10 and w > 10 and h >= 3 and w > h:
            cx = x + (w // 2)
            
            # Fereastra de decupare ROI - o centram mai bine injurul / sub text, dar oprim box-ul sa ia iarba.
            # Daca metinul nu e mereu direct sub text, facem boxul destul de mare
            box_width = 20
            box_height = 20
            
            # Deplasăm zona de căutare să fie și stânga/dreapta/sus față de text, 
            # fiindca metinul s-ar putea să ocupe o poziție ciudată
            cy = y + (h // 2)
            roi_x1 = max(0, cx - box_width // 2)
            roi_y1 = max(0, cy - 40) # cauta si deasupra textului in caz ca e in fata
            roi_x2 = min(width, roi_x1 + box_width)
            roi_y2 = min(height, roi_y1 + box_height)
            
            roi = img[roi_y1:roi_y2, roi_x1:roi_x2]
            
            best_cx = cx
            best_cy = y + h + 20 # default
            
            # Randam albastru pt bounding box-ul textului
            cv2.rectangle(output_img, (x, y), (x+w, y+h), (255, 0, 0), 2)
            # Randam un dreptunghi galben pt ROI
            cv2.rectangle(output_img, (roi_x1, roi_y1), (roi_x2, roi_y2), (0, 255, 255), 2)

            if roi.size > 0:
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
                
                # Revenim la praguri mici la Canny (ex: 20, 60), dar folosim filtrare geometricala
                edges = cv2.Canny(blurred, 20, 60)
                
                kernel_roi = np.ones((5, 5), np.uint8)
                closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel_roi)
                
                # Punem masca "closed" in masca generala pt a vedea ce a vazut Canny
                h_roi, w_roi = closed.shape
                debug_mask[roi_y1:roi_y1+h_roi, roi_x1:roi_x1+w_roi] = cv2.bitwise_or(
                    debug_mask[roi_y1:roi_y1+h_roi, roi_x1:roi_x1+w_roi], closed)

                roi_contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                max_area = 0
                for r_cnt in roi_contours:
                    r_area = cv2.contourArea(r_cnt)
                    rx, ry, rw, rh = cv2.boundingRect(r_cnt)
                    
                    # FILTRU in loc de threshold mare: Metinele au corp destul de compact
                    # iarba e de obicei imprastiata ciudat (foarte lata / foarte joasa)
                    # Verificam ca formatul sa fie gen "piatra" (ratio 0.4 - 1.8), +inaltime minima
                    ratio = rw / float(rh) if rh > 0 else 0
                    
                    if r_area > 100 and r_area > max_area and 0.4 < ratio < 1.8 and rh >= 25 and rw >= 25:
                        # Excludem daca muchia detectata curprinde fix aria textului 
                        # pt ca textul alb genereaza margini extrem de clare
                        if ry + rh > (y - roi_y1): 
                            max_area = r_area
                            
                            best_cx = roi_x1 + rx + (rw // 2)
                            best_cy = roi_y1 + ry + (rh // 2)
                            
                            # Rosu pt body-ul validat
                            cv2.rectangle(output_img, (roi_x1+rx, roi_y1+ry), (roi_x1+rx+rw, roi_y1+ry+rh), (0, 0, 255), 2)
            
            # Verde pt click efectiv
            cv2.circle(output_img, (int(best_cx), int(best_cy)), 6, (0, 255, 0), -1)

    cv2.imwrite("test_snake_roi_output.png", output_img)
    cv2.imwrite("test_snake_roi_mask.png", debug_mask)
    cv2.imwrite("test_snake_text_mask.png", clean_mask)
    
    print("Au fost salvate noile imagini de debug:")
    print(" - test_snake_roi_output.png -> Cu patratele desenate, centrul (verde) si ROI (galben).")
    print(" - test_snake_roi_mask.png   -> Masca Edge/Canny cu ce muchii s-au gasit pt Metin.")
    print(" - test_snake_text_mask.png  -> Masca initiala pt text.")

if __name__ == "__main__":
    test_snake_roi()