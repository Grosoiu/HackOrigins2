import cv2
import numpy as np
import pyautogui

# citire imagine (screenshot)
img = cv2.imread("test.png")
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# convertim culoarea target în HSV
target_bgr = np.uint8([[[93, 231, 121]]])  # BGR (OpenCV)
target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0][0]

# toleranta (am marit plaja pentru a prinde nuantele textului mai bine)
lower = np.array([max(0, target_hsv[0]-3), 50, 50])
upper = np.array([min(179, target_hsv[0]+3), 255, 255])

mask = cv2.inRange(hsv, lower, upper)

# unire text (in loc sa folosim MORPH_OPEN care sterge liniile subtiri ale textului,
# folosim dilatare cu un kernel lat pentru a uni literele intr-un singur contur)
kernel_text = np.ones((5, 20), np.uint8)
mask = cv2.dilate(mask, kernel_text, iterations=1)

# gasim contururi
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

for cnt in contours:
    x,y,w,h = cv2.boundingRect(cnt)
    
    # Textul este in mod normal mai lung decat inalt, asa ca folosim raportul w/h
    if w*h > 50 and w > h * 3.7:  # eliminam noise-ul mic si formele patratoase
        cx = x + w//2
        cy = y + h//2 + 20 # cu 20 pixeli mai jos
        
        print("Zacamant detectat la:", cx, cy)

        # Desenam marker (dreptunghi pe text si punct de click) pentru debug vizual
        cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.circle(img, (cx, cy), 5, (0, 0, 255), -1)

        # CLICK automat
        pyautogui.click(cx, cy)

# vizualizare
cv2.imshow("mask", mask)
cv2.imshow("result", img)
cv2.waitKey(0)
cv2.destroyAllWindows()