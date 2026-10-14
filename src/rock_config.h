#pragma once
#include <stdint.h>

// Local gesture tuning: a short spin each way, with time to reverse naturally.
namespace rock_config {
constexpr int32_t MAX_DETENTS = 12;
constexpr uint32_t MIN_REVERSAL_MS = 45;  // retain contact-bounce rejection
constexpr uint32_t REVERSAL_MS = 1500;
constexpr uint32_t NEW_RUN_MS = 2000;
constexpr uint32_t SETTLE_MS = 300;       // wait until the hand stops turning
}
