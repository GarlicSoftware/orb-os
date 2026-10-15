# Relaxed rock gesture

Local build `2.17.01-relaxed-rock.6`, based on Orb OS 2.17.01.

Turn a short distance either way, reverse, then stop. Both halves can span up to
12 detected clicks. The reversal can take up to 1.5 seconds, instead of 250 ms.
The menu opens after 300 ms without another detected click. A pause over 2 seconds
starts a new run. The 45 ms contact-bounce guard remains in place.

The limits live in `src/rock_config.h` and are shared by the device encoder,
desktop encoder, and menu router. The router's idle tick now dispatches a completed
gesture instead of consuming it during a preliminary state check.

Back-and-forth scrolling outside Settings may also open the menu with these wider limits.
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

## Settings navigation

In `.5`, Settings receives turns directly, without the rock detector holding or
discarding direction changes. This applies to its lists and value editors; use
Back to leave Settings. The forgiving rock gesture remains available elsewhere.
Saving master, tick, or chime volume returns to Sound, with the same volume item
selected, instead of opening the app switcher. Volume persistence and the master
volume preview are retained.
Regression tests exercise immediate Settings reversals and consume stale gestures
on exit. `tests/run_volume_return.py` checks the actual save branch for all three
targets at levels 0, 50, and 100, including persistence, Sound return, and preview.

## Clock button

In `.6`, pressing the knob while viewing Clock immediately opens the app menu.
This also works while the clock needs winding or a rock gesture is settling.
An old gesture-help overlay is dismissed and the same press opens the menu.
Once browsing, the button selects the highlighted app as usual. Settings and
other apps keep their own button actions. USB `press` now uses the physical
button's input-router path so these behaviors can be verified on the device.

## Build and verify

In `.4`, the Settings renderer clips each unrotated glyph to its actual rectangle
instead of scanning a square around the glyph diagonal for all 24 glow copies.
Row interpolation coordinates are computed once per row; horizontal coordinates
are cached in 768 bytes of shared scratch for ordinary-width glyphs, with the
original calculation retained for larger glyphs. The glyph, glow,
opacity, and overlap calculations produce byte-identical output in 400 comparison
cases against commit `3291ca4`, including fractional coordinates and clipping.
Run `python tests/run_settings_blit.py` from a Visual Studio developer prompt.
On the physical Orb with Aviator, a matched six-turn Settings sequence from the
top-level list dropped from a median 547 ms to 297 ms in USB command handling
(about 46% less time). This measures the Settings handler, not complete
input-to-visible-display latency. The final app upload's hash verified.

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
