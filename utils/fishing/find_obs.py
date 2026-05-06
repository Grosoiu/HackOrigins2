import win32gui

def find_obs_windows():
    print("Scanning for OBS-related windows...")
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            # Filter for windows that have OBS or Projector in the title
            if title and ("OBS" in title.upper() or "PROJECTOR" in title.upper()):
                print(f"Found window: '{title}'")
                
    win32gui.EnumWindows(callback, None)

if __name__ == "__main__":
    find_obs_windows()