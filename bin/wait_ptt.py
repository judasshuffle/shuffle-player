#!/usr/bin/env python3
import sys, time
from gpiozero import Button

def main():
    pin = int(sys.argv[1]) if len(sys.argv) > 1 else 17
    b = Button(pin, pull_up=True, bounce_time=0.05)

    # Ensure we start from "released" state (prevents instant triggers)
    while b.is_pressed:
        time.sleep(0.02)

    # Wait for an actual press
    b.wait_for_press()

    # Require a deliberate press (debounce noise / phantom taps)
    t0 = time.time()
    while b.is_pressed and (time.time() - t0) < 0.15:
        time.sleep(0.01)

    # If it released too quickly, treat as noise and wait again
    if not b.is_pressed:
        return main()

    # Now wait for release to end the PTT cycle
    b.wait_for_release()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
