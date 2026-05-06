import cv2
import os
import time
import numpy as np

def detect_fish(camera_index=1):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    
    if not cap.isOpened():
        print(f"Failed to open camera index {camera_index}")
        return

    # Target resolution
    width, height = 1366, 768
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    center_x, center_y = width // 2, height // 2
    radius = 62

    # Fish color thresholds (Note: OpenCV uses BGR format, not RGB)
    # RGB: (61, 96, 123) -> BGR: (123, 96, 61)
    # RGB: (62, 94, 122) -> BGR: (122, 94, 62)
    # Adding a +/- 20 tolerance for variations in lighting/shading inside the circle
    lower_color = np.array([115, 85, 55], dtype=np.uint8)
    upper_color = np.array([125, 95, 65], dtype=np.uint8)

    output_dir = os.path.join(os.path.dirname(__file__), "captures")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("Starting fish detection loop. Press Ctrl+C in terminal to stop.")
    
    try:
        while True:
            start_time = time.time()
            ret, frame = cap.read()
            if not ret:
                print("Failed to capture frame.")
                break

            # Create a blank mask for the circle (all black)
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            # Draw a filled white circle in the center
            cv2.circle(mask, (center_x, center_y), radius, 255, -1)

            # Mask the frame so we ONLY process pixels inside the center circle
            circle_roi = cv2.bitwise_and(frame, frame, mask=mask)

            # Find pixels in our fish BGR color range
            color_mask = cv2.inRange(circle_roi, lower_color, upper_color)

            # Find contours (shapes) of the detected color
            contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            fish_detected = False
            for cnt in contours:
                # Filter out tiny noise (only shapes larger than 5 pixels)
                if cv2.contourArea(cnt) > 5:
                    x, y, w, h = cv2.boundingRect(cnt)
                    # Highlight the fish position with a red rectangle
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2) 
                    cv2.putText(frame, "FISH", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                    fish_detected = True

            # Draw the main tracking circle boundary for visual debugging (in green)
            cv2.circle(frame, (center_x, center_y), radius, (0, 255, 0), 2) 

            if fish_detected:
                timestamp = int(time.time() * 1000)
                save_path = os.path.join(output_dir, f"fish_detected_{timestamp}.png")
                cv2.imwrite(save_path, frame)
                print(f"Fish detected! Saved to {save_path}")

            # Ensure we strictly check every ~100ms
            elapsed = time.time() - start_time
            sleep_time = max(0.1 - elapsed, 0)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        cap.release()

if __name__ == "__main__":
    target_camera_index = 1 
    detect_fish(target_camera_index)