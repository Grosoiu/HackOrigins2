import pymem
import pymem.process

def main():
    try:
        # 1. Attach to the game process
        pm = pymem.Pymem("Origins.exe")
        
        # 2. Get the base address of the Origins.exe module
        module = pymem.process.module_from_name(pm.process_handle, "Origins.exe")
        base_addr = module.lpBaseOfDll
        
        # Base pointer from your Cheat Engine file: Origins.exe+3686698
        static_ptr = base_addr + 0x3686698
        
        # Helper function to resolve pointers
        # Note: Metin2 clients are generally 32-bit, so we use read_int (4 bytes) to read pointers.
        # If the game is 64-bit, you must change `pm.read_int` to `pm.read_longlong`
        def get_pointer_addr(base, offsets):
            addr = pm.read_int(base)
            for offset in offsets[:-1]:
                addr = pm.read_int(addr + offset)
            return addr + offsets[-1]

        # NOTE: Cheat Engine XML saves offsets in reverse order (bottom to top).
        # E.g., <Offset>8</Offset> then <Offset>14</Offset> translates to offsets [0x14, 0x8]

        # ----------------------------------------------------
        # 1. is_monuted [Byte] - Offsets: 0x14, 0x8
        # ----------------------------------------------------
        addr_is_mounted = get_pointer_addr(static_ptr, [0x14, 0x8])
        
        # Read a Byte
        is_mounted_val = pm.read_bytes(addr_is_mounted, 1)[0]
        print(f"is_mounted: {is_mounted_val}")
        
        # Write a Byte (uncomment to test)
        pm.write_bytes(addr_is_mounted, bytes([1]), 1) 

        # ----------------------------------------------------
        # 4. attsp [2 Bytes] - Offsets: 0x14, 0x71A
        # ----------------------------------------------------
        addr_attsp = get_pointer_addr(static_ptr, [0x14, 0x71A])
        
        # Read a 2-Byte Short
        attsp_val = pm.read_short(addr_attsp)
        print(f"attsp: {attsp_val}")
        
        # Write a 2-Byte Short (uncomment to test)
        # pm.write_short(addr_attsp, 16300)

        # ----------------------------------------------------
        # Other Pointers
        # ----------------------------------------------------
        # horse_WH [Byte] (0x14, 0xC, 0x594)
        addr_horse_wh = get_pointer_addr(static_ptr, [0x14, 0x0C, 0x594])
        
        # player_WH [Byte] (0x14, 0x7F8)
        addr_player_wh = get_pointer_addr(static_ptr, [0x14, 0x7F8])
        
        # combo [2 Bytes] (0x14, 0x668)
        addr_combo = get_pointer_addr(static_ptr, [0x14, 0x668])

    except pymem.exception.ProcessNotFound:
        print("Origins.exe is not running.")
    except pymem.exception.MemoryReadError as e:
        print(f"Error reading memory: {e}")

if __name__ == "__main__":
    main()