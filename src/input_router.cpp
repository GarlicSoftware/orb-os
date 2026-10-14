#include "input_router.h"
#include "knob_help.h"
#include "wind_notice.h"
#include "update_ui.h"
#include <lvgl.h>       // lv_tick_get — a millisecond clock both targets have
#if defined(ESP_PLATFORM)
#include "display.h"   // markInput — input-to-glass timing
#endif
#include "app_shell.h"
#include "knob.h"
#include "rock_config.h"

// What the knob does, in one place, shared by the device (main.cpp) and the simulator
// (sim_main.cpp) so "it behaved right in the sim" means "it behaves right on the Orb".
//
// THE ROCK
//
// Turning used to open the app switcher. That made the knob useless for anything else:
// every app that wanted a turn of its own had to first be given the knob by a button press,
// and this button takes real force to click. So the knob had one job and the button had all
// the others, which is backwards for a device whose only control is a knob.
//
// Turns normally belong to the app. A short spin each way opens the switcher;
// the relaxed local profile allows up to 12 clicks and 1.5 seconds to reverse.
// This also means back-and-forth scrolling inside an app may open the menu.
namespace {

// Match the encoder's generous reversal window and allow a short spin on both sides.
constexpr uint32_t ROCK_WINDOW_MS = rock_config::REVERSAL_MS;
constexpr uint32_t ROCK_SETTLE_MS = rock_config::SETTLE_MS;
constexpr int32_t ROCK_BACK_MAX = rock_config::MAX_DETENTS;
uint32_t s_settleRockAt = 0;
uint32_t s_lastMotionAt = 0;
int32_t s_lastMotionDetent = 0;

// The reversal this router has already acted on, so one gesture cannot fire twice. Stored
// as the timestamp rather than a flag: a second rock produces a new one, so it fires again
// with nothing to arm or reset.
uint32_t s_firedAt = 0;
// Detents held back while a reversal settles; delivered if it turns out not to be a rock.
int32_t  s_held = 0;

enum Rock { ROCK_NONE, ROCK_PENDING, ROCK_FIRE, ROCK_REJECT };

Rock rock_state() {
    const uint32_t at = knob::lastRockMs();
    if (at == 0) return ROCK_NONE;                   // no reversal has ever happened
    if (at == s_firedAt) return ROCK_NONE;           // already acted on this one
    if (knob::lastRockGapMs() > ROCK_WINDOW_MS) {    // a reversal, but an unhurried one
        s_firedAt = at;                              // consumed, so it cannot fire later
        return ROCK_NONE;
    }
    const int32_t after = knob::detentCount() - knob::lastRockDetent();
    const int32_t back  = (after < 0 ? -after : after) + 1;   // the reversal detent counts
    if (back > ROCK_BACK_MAX) { s_firedAt = at; return ROCK_REJECT; }
    const uint32_t now = lv_tick_get();
    const int32_t position = knob::detentCount();
    if (s_settleRockAt != at) {
        s_settleRockAt = at;
        s_lastMotionAt = now;
        s_lastMotionDetent = position;
    } else if (position != s_lastMotionDetent) {
        s_lastMotionAt = now;
        s_lastMotionDetent = position;
    }
    if ((uint32_t)(now - s_lastMotionAt) < ROCK_SETTLE_MS) return ROCK_PENDING;
    s_firedAt = at;
    return ROCK_FIRE;
}


}  // namespace

// A reversal that is settling needs a poll with no new input to finish settling. main.cpp
// and the simulator call this every pass; it is a no-op unless a reversal is in flight.
void input_router::tick() {
    // dispatch owns consumption: probing rock_state here could swallow ROCK_FIRE.
    if (knob::lastRockMs() != 0 && knob::lastRockMs() != s_firedAt) dispatch(0, false);
}

void input_router::dispatch(int delta, bool pressed) {
    // The "Ready" notice owns the knob until it is acknowledged, and ANY input clears it:
    // a turn either way or a press. It used to demand a press specifically, which made a
    // notice that exists to say "the knob is yours again" the one screen where most of the
    // knob did nothing. Reaching for a control and having it ignore you is the exact
    // feeling this notice is here to end.
    //
    // Whichever input clears it is SWALLOWED rather than passed on. Letting it through
    // would mean the gesture that means "yes, I see it" also does whatever the clock does
    // with it, which is the sort of thing that teaches people not to trust a confirmation.
    if (update_ui::awaitingAck()) {
        if (pressed || delta != 0) update_ui::ackReady();
        return;
    }
    // What the knob does, put up because a press had nowhere to go. Same contract as the
    // notice above and for the same reason: any input clears it, and that input is
    // SWALLOWED. Letting the dismissing press through would hand it straight back to the
    // screen that ignored it, which is the silence this panel exists to break.
    if (knob_help::showing()) {
        if (pressed || delta != 0) knob_help::dismiss();
        return;
    }
    // Stamped here rather than in the menu, because "how long until I see it" is a question
    // worth being able to ask of any screen. The first attempt timed only the switcher, on
    // the assumption that the switcher was the problem, which is the assumption being
    // tested. Cleared by whichever frame lands next; see display::markInput.
    // Device only. The simulator draws through its own SDL path and has no display.cpp, and
    // "how long until the panel shows it" is not a question a desktop window can answer
    // anyway. lv_tick_get rather than millis() because this file has no Arduino header;
    // lv_conf.h maps LVGL's tick straight onto millis() on the device, so it is the same
    // counter the flush reads.
#if defined(ESP_PLATFORM)
    if (delta != 0 || pressed) display::markInput(lv_tick_get());
#endif

    // Once the switcher is open, every click belongs to it immediately. Do not
    // hold a reversal for gesture detection or discard it when a rock settles.
    if (app_shell::browsing()) {
        s_firedAt = knob::lastRockMs();
        s_held = 0;
        if (delta != 0) app_shell::browseTurn(delta);
        if (pressed) app_shell::browsePress();
        return;
    }

    // Settings owns turns for navigation and editing, including reversals.
    // Its Back controls provide an explicit exit to the app switcher.
    if (app_shell::index() == app_shell::APP_SETTINGS) {
        s_firedAt = knob::lastRockMs();
        s_held = 0;
        if (delta != 0) app_shell::turnCurrent(delta);
        if (pressed) app_shell::pressCurrent();
        return;
    }

    // A wound-down clock asking to be wound. Turning winds it; a press does nothing,
    // because five turns is the price and a press would be a way to skip it.
    //
    // The rock is checked FIRST and deliberately still works, so this screen can always be
    // left. Winding counts detents in one direction only, which is what leaves a reversal
    // free to keep meaning "open the app menu" here as everywhere else. Without that, a
    // theme could strand somebody on a screen that will not take no for an answer, which is
    // the thing CUT-05 exists to forbid.
    // The reversal, settled or not. While it settles the detents are held; when it turns
    // out to be a scroll they are let through with this poll's, and when it is a rock they
    // are dropped, because the detents that MADE the gesture are not input to the app.
    const Rock rock = rock_state();
    if (rock == ROCK_PENDING) { s_held += delta; delta = 0; }
    else if (rock == ROCK_REJECT) { delta += s_held; s_held = 0; }
    else if (rock == ROCK_FIRE) { s_held = 0; }

    if (wind_notice::showing()) {
        if (rock == ROCK_FIRE) { app_shell::openSwitcher(); return; }
        if (delta != 0) wind_notice::turn(delta);
        return;
    }

    // Checked before the turn is delivered, so the detents that MADE the gesture are not
    // also handed to the app underneath. Without this, rocking out of the flight tracker
    // would select an aircraft on the way past.
    //
    // The gesture opens the switcher from other apps, including captured screens.
    // Settings is routed above, so ordinary navigation cannot be mistaken for exit.
    if (rock == ROCK_FIRE) {
        app_shell::openSwitcher();
        return;
    }

    if (delta != 0) app_shell::turnCurrent(delta);
    // A press the current screen had no use for is not nothing happening, it is somebody
    // asking what this control does. The clock is the case that matters: it registers no
    // press handler, so on the first screen a new Orb ever shows, the most obvious thing to
    // try has always done nothing at all.
    //
    // Asked of the shared path rather than of the clock, so it cannot drift. Any screen that
    // ignores a press gets the same answer, and a screen that grows a handler stops giving
    // it without anybody having to remember this line exists.
    //
    // `count() > 0` is not belt and braces, it is the difference between the two ways a
    // press can go unanswered. Before the roster registers there is no screen that could
    // have ignored anything: the boot splash is still on the glass and the device has not
    // yet asked to be driven, so a press then is EARLY rather than lost, and covering the
    // splash with instructions would be answering a question nobody asked. Caught by the
    // --knobshot harness, which pressed at 2500 ms, got the panel, and passed while proving
    // nothing at all about the clock.
    if (pressed && !app_shell::pressCurrent() && app_shell::count() > 0) knob_help::show();
}
