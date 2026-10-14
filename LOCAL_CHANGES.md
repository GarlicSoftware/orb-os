# Relaxed rock gesture

Local build `2.17.01-relaxed-rock.3`, based on Orb OS 2.17.01.

Turn a short distance either way, reverse, then stop. Both halves can span up to
12 detected clicks. The reversal can take up to 1.5 seconds, instead of 250 ms.
The menu opens after 300 ms without another detected click. A pause over 2 seconds
starts a new run. The 45 ms contact-bounce guard remains in place.

The limits live in `src/rock_config.h` and are shared by the device encoder,
desktop encoder, and menu router. The router's idle tick now dispatches a completed
gesture instead of consuming it during a preliminary state check.

Back-and-forth scrolling in an app may also open the menu with these wider limits.
Pressing selects the highlighted app. The app menu stays open until you press;
the original two-second automatic selection timer has been removed in `.3`.
Verified on the board by opening the app menu, moving to another item, and waiting
five seconds: the switcher remained open and the underlying app did not change.
The USB `apps` reply now includes `browsing` for checking this state directly.

## Immediate menu turns

Once the menu is open, each click now reaches it without going through the rock
detector. Previously, reversing direction while browsing could hold input for the
gesture's settle period and discard the held turns when it recognized a rock.
The router also consumes those menu-time gesture timestamps so they cannot reopen
the menu after selecting an app. One detected click still moves one menu item.

Regression tests assert delivery on every menu click in both directions, including
reversals, and verify that no deferred rock fires after leaving the menu.

## Build and verify

```powershell
python -m platformio run -e esp32-s3-amoled-175
```

From a Visual Studio developer prompt:

```powershell
python tests/run_relaxed_rock.py
```

The host regression harness uses the device's detent handler and actual router
with hardware and UI stubs. It covers slow and multiple-click reversals in both
directions, completion without further input, duplicate suppression, the original
one-click gesture, long-scroll rejection, pause rejection, bounce rejection, and
turns while browsing the menu. The firmware build passed, the USB upload's hash
verified, and the owner confirmed the initial relaxed-gesture build works on the
physical Orb on October 14, 2026. A later controlled capture recorded five presses
with the app switcher already open. The `.2` menu-response fix has host regression
coverage; its physical responsiveness still needs confirmation after installation.

## Firmware and rollback

`local-firmware/original-app.bin` is a readback of the original app partition.
`local-firmware/relaxed-rock.bin` is the modified app image. These are app-only
images for address `0x10000`, not merged images for address zero.

Write only the app with esptool; do not erase the chip. This preserves NVS settings,
the partition table, and cached theme artwork. Files on the SD card are unaffected.
To undo the change, write `original-app.bin` at `0x10000`.

Installing stock firmware through Orb Studio will replace this custom gesture.
