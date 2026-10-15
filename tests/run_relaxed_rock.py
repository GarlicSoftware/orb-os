"""Host regression tests using the device's actual detent and routing code.

Run from a Visual Studio developer prompt: python tests/run_relaxed_rock.py
Only hardware IO and the UI are stubbed; gesture logic comes from src/.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
knob = (root / 'src/knob.cpp').read_text(encoding='utf-8')
knob = knob[knob.index('// --- Wiring'):knob.index('static void IRAM_ATTR knob_isr()')]
with tempfile.TemporaryDirectory(prefix='orb-rock-test-') as directory:
    work = Path(directory)
    (work / 'lvgl.h').write_text('#pragma once\n#include <stdint.h>\nstruct lv_obj_t {};\nuint32_t lv_tick_get();\n')
    harness = r'''
#include <stdint.h>
#include <cassert>
#include <iostream>
#include "rock_config.h"
#define IRAM_ATTR
#define HIGH 1
uint32_t testNow = 10000;
int opens = 0, delivered = 0;
bool browsingNow = false, settingsNow = false;
bool windShowing = false, helpShowing = false;
int helpCalls = 0, pressCalls = 0, browsePressCalls = 0, ordinaryApp = 0;
uint64_t esp_timer_get_time() { return uint64_t(testNow) * 1000; }
uint32_t lv_tick_get() { return testNow; }
'''+knob+r'''
#include "knob.h"
uint32_t knob::lastRockMs() { return s_rockMs; }
uint32_t knob::lastRockGapMs() { return s_rockGapMs; }
int32_t knob::lastRockDetent() { return s_rockDetent; }
int32_t knob::detentCount() { return s_detent; }
#include "input_router.cpp"
bool update_ui::awaitingAck() { return false; }
void update_ui::ackReady() {}
bool knob_help::showing() { return helpShowing; }
void knob_help::show() { ++helpCalls; helpShowing=true; }
void knob_help::dismiss() { helpShowing=false; }
bool wind_notice::showing() { return windShowing; }
void wind_notice::turn(int) {}
bool app_shell::browsing() { return browsingNow; }
int app_shell::index() { return settingsNow ? app_shell::APP_SETTINGS : ordinaryApp; }
void app_shell::browseTurn(int d) { delivered += d; }
void app_shell::browsePress() { ++browsePressCalls; browsingNow=false; }
void app_shell::openSwitcher() { ++opens; browsingNow = true; }
void app_shell::turnCurrent(int d) { delivered += d; }
bool app_shell::pressCurrent() { ++pressCalls; return true; }
int app_shell::count() { return 4; }
void reset() {
    testNow += 5000;
    opens = delivered = 0; browsingNow = settingsNow = false;
    windShowing=helpShowing=false;
    helpCalls=pressCalls=browsePressCalls=ordinaryApp=0;
    s_detent = s_rockDetent = s_isrLastDir = s_isrRunLen = 0;
    s_isrLastDirMs = s_rockMs = s_rockGapMs = 0;
    s_firedAt = s_settleRockAt = s_lastMotionAt = 0;
    s_held = s_lastMotionDetent = 0;
}
void turn(int dir, int count, uint32_t interval = 80) {
    for (int i=0; i<count; ++i) {
        testNow += interval;
        on_detent(dir);
        const int before = delivered;
        const bool wasBrowsing = browsingNow || settingsNow;
        input_router::dispatch(dir, false);
        if (wasBrowsing) assert(delivered == before + dir); // each click, no settle delay
        input_router::tick();
    }
}
void settle() { testNow += 301; input_router::tick(); }
int main() {
    reset(); turn(-1,6); testNow += 900; turn(1,6);
    assert(opens == 0); settle(); assert(opens == 1);
    input_router::tick(); assert(opens == 1); // no duplicate opening
    reset(); turn(1,12); testNow += 1300; turn(-1,12);
    assert(opens == 0); settle(); assert(opens == 1); // either direction, many clicks
    reset(); turn(-1,1); turn(1,1); settle(); assert(opens == 1); // original gesture
    reset(); turn(-1,13); turn(1,1); settle(); assert(opens == 0); // long scroll
    reset(); turn(-1,6); testNow += 1600; turn(1,6); settle(); assert(opens == 0);
    reset(); turn(-1,6); turn(1,13); settle(); assert(opens == 0); assert(s_held == 0);
    reset(); turn(-1,1); turn(1,1,10); settle(); assert(opens == 0); // bounce guard
    reset(); turn(1,10); settle(); assert(opens == 0); assert(delivered == 10);
    reset(); browsingNow = true; turn(-1,6); turn(1,6); settle(); assert(opens == 0);
    assert(s_held == 0); assert(s_firedAt == s_rockMs);
    browsingNow = false; settle(); assert(opens == 0); // no stale gesture after selection
    reset(); settingsNow = true; turn(1,1); testNow += 850; turn(-1,1);
    settle(); assert(opens == 0); assert(s_held == 0);
    turn(1,6); testNow += 1000; turn(-1,6); settle(); assert(opens == 0);
    settingsNow = false; settle(); assert(opens == 0); // no deferred gesture on Settings exit
    reset(); input_router::dispatch(0,true);
    assert(opens==1 && helpCalls==0 && pressCalls==0);
    input_router::dispatch(0,true); assert(browsePressCalls==1 && opens==1);
    reset(); windShowing=true; input_router::dispatch(0,true);
    assert(opens==1 && helpCalls==0);
    reset(); helpShowing=true; input_router::dispatch(0,true);
    assert(opens==1 && !helpShowing);
    reset(); turn(-1,1); turn(1,1); input_router::dispatch(0,true);
    assert(opens==1 && s_held==0); settle(); assert(opens==1);
    reset(); settingsNow=true; input_router::dispatch(0,true);
    assert(opens==0 && pressCalls==1);
    reset(); ordinaryApp=app_shell::APP_INTEL; input_router::dispatch(0,true);
    assert(opens==0 && pressCalls==1);
    std::cout << "PASS: menu and Settings reversals delivered immediately; outside gestures still work\n";
}
'''
    (work / 'test.cpp').write_text(harness, encoding='utf-8')
    subprocess.run(['cl', '/nologo', '/EHsc', '/std:c++17', '/D APPS_LAUNCH_ONE=1',
                    '/I'+str(root/'src'), '/I'+str(work), 'test.cpp', '/Fe:test.exe'], cwd=work, check=True)
    subprocess.run([str(work/'test.exe')], cwd=work, check=True)
