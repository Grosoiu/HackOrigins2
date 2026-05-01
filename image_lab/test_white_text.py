import cv2
import numpy as np

def test_detect_white_text():
    # 1. Incarca imaginea
    img_path = "image_lab/img.png"
    img = cv2.imread(img_path)
    if img is None:
        print(f"Eroare: Nu s-a putut incarca {img_path}.")
        return

    height, width = img.shape[:2]

    # 2. Margini - evitam marginile cu 20% pentru a cauta doar in centrul ecranului
    margin_y = int(height * 0.2)
    margin_x = int(width * 0.2)
    
    # Cream o masca de regiune interesata
    roi_mask = np.zeros((height, width), dtype=np.uint8)
    roi_mask[margin_y:height-margin_y, margin_x:width-margin_x] = 255

    # 3. Detectie culoare alb curat (255, 255, 255)
    # Lasam o marja foarte mica pentru a prinde și ușoare difracții (esantionare compresie), ex. 240+
    lower_white = np.array([245, 245, 245], dtype=np.uint8)
    upper_white = np.array([255, 255, 255], dtype=np.uint8)
    
    # Cream masca pentru alb
    color_mask = cv2.inRange(img, lower_white, upper_white)

    # 4. Combinam mastile (Vrem doar albul din afara zonei de top 30%)
    final_mask = cv2.bitwise_and(color_mask, roi_mask)

    # 5. Clean-up morofologic - conecteaza literele intre ele ca sa formam cuvinte/blocuri de text
    # Folosim doar dilatare pentru a nu sterge pixelii subtiri ai literelor
    kernel_text = np.ones((2, 10), np.uint8)
    
    clean_mask = cv2.dilate(final_mask, kernel_text, iterations=1)

    # 6. Gasim contururile pentru zonele de text alb
    contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    result_img = img.copy()

    for cnt in contours:
        area = cv2.contourArea(cnt)
        x, y, w, h = cv2.boundingRect(cnt)
        
        # Filtram sa aiba forma subtire si lata (cum arata textul metinelor)
        # Reducem limitele pentru ca scrisul este foarte mic
        if area > 10 and w > 10 and h >= 3 and w > h:
            # Coloram textul determinat cu Rosu in poza rezultat
            cv2.rectangle(result_img, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(result_img, "Metin Text", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # 7. Salveaza imaginile pentru a putea analiza rezultatul
    cv2.imwrite("image_lab/mask_output.png", clean_mask)
    cv2.imwrite("image_lab/result_output.png", result_img)
    
    print("A fost creat 'image_lab/mask_output.png' pentru masca de alb curat.")
    print("A fost creat 'image_lab/result_output.png' cu dreptunghiuri pe masca gasita.")

if __name__ == "__main__":
    test_detect_white_text()
