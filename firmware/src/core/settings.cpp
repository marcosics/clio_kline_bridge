#include "settings.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "util.h"

static const uint32_t MAGIC = 0xC110C0DE;
static const uint16_t VERSION = 2;
extern Hal* gPlatform;

static uint32_t crc32(const uint8_t* p, size_t n) {
  uint32_t c = 0xFFFFFFFF;
  while (n--) {
    c ^= *p++;
    for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320 & (0 - (c & 1)));
  }
  return ~c;
}

static void copy(char* dst, size_t n, const char* src) {
  strncpy(dst, src, n - 1);
  dst[n - 1] = 0;
}

void settingsDefaults(Settings& s) {
  s = Settings();   // todo a cero (value-initialization)
  s.magic = MAGIC;
  s.version = VERSION;
  copy(s.staSsid, sizeof s.staSsid, STA_SSID);
  copy(s.staPass, sizeof s.staPass, STA_PASS);
  copy(s.apSsid, sizeof s.apSsid, WIFI_SSID);
  copy(s.apPass, sizeof s.apPass, WIFI_PASS);
  copy(s.host, sizeof s.host, HOSTNAME);
  s.ecu = DEFAULT_ECU;
  s.tester = TESTER_ADDR;
  s.baud = DEFAULT_BAUD;
  s.t = Timing();
  s.kaMs = 1500;
  s.retries = 1;
  s.logLevel = 1;
  s.expectEcho = 1;
  s.apAlways = 1;
  s.autoKa = 1;
}

bool settingsLoad(Settings& s) {
  Settings x;
  if (gPlatform && gPlatform->loadBlob(&x, sizeof x) && x.magic == MAGIC && x.version == VERSION &&
      x.crc == crc32((const uint8_t*)&x, offsetof(Settings, crc))) {
    s = x;
    s.staSsid[SSID_LEN - 1] = s.apSsid[SSID_LEN - 1] = s.staPass[PASS_LEN - 1] = s.apPass[PASS_LEN - 1] = 0;
    s.host[HOST_LEN - 1] = 0;
    return true;
  }
  settingsDefaults(s);
  return false;
}

bool settingsSave(const Settings& s) {
  Settings x = s;
  x.magic = MAGIC;
  x.version = VERSION;
  x.crc = crc32((const uint8_t*)&x, offsetof(Settings, crc));
  return gPlatform && gPlatform->saveBlob(&x, sizeof x);
}

struct U16Key { const char* k; size_t off; uint16_t lo, hi; };
static const U16Key U16[] = {
  {"P1MAX", offsetof(Timing, p1max), 1, 1000}, {"P2MAX", offsetof(Timing, p2max), 10, 5000},
  {"P2EXT", offsetof(Timing, p2ext), 100, 60000}, {"P3MIN", offsetof(Timing, p3min), 0, 5000},
  {"P4", offsetof(Timing, p4), 0, 50}, {"W5", offsetof(Timing, w5), 0, 5000},
  {"TINIL", offsetof(Timing, tinil), 5, 100}, {"TWUP", offsetof(Timing, twup), 10, 200},
};

bool settingsSet(Settings& s, const char* key, const char* val, char* err, size_t errn) {
  uint32_t v = 0;
  if (!val) val = "";
  if (!strcmp(key, "STA_SSID")) { copy(s.staSsid, sizeof s.staSsid, val); return true; }
  if (!strcmp(key, "STA_PASS")) { copy(s.staPass, sizeof s.staPass, val); return true; }
  if (!strcmp(key, "AP_SSID")) { if (!*val) { snprintf(err, errn, "AP_SSID vacio"); return false; } copy(s.apSsid, sizeof s.apSsid, val); return true; }
  if (!strcmp(key, "AP_PASS")) {
    if (*val && strlen(val) < 8) { snprintf(err, errn, "AP_PASS: minimo 8 caracteres (o vacia = red abierta)"); return false; }
    copy(s.apPass, sizeof s.apPass, val); return true;
  }
  if (!strcmp(key, "HOST")) { copy(s.host, sizeof s.host, val); return true; }
  if (!strcmp(key, "ECU") || !strcmp(key, "TESTER")) {
    if (!parseU32(val, &v, 16) || v > 0xFF) { snprintf(err, errn, "%s: hex 00-FF", key); return false; }
    (key[0] == 'E' ? s.ecu : s.tester) = (uint8_t)v; return true;
  }
  if (!strcmp(key, "BAUD")) {
    if (!parseU32(val, &v) || v < 1200 || v > 115200) { snprintf(err, errn, "BAUD 1200-115200"); return false; }
    s.baud = v; return true;
  }
  for (const U16Key& k : U16) {
    if (strcmp(key, k.k)) continue;
    if (!parseU32(val, &v) || v < k.lo || v > k.hi) { snprintf(err, errn, "%s: %u-%u ms", k.k, k.lo, k.hi); return false; }
    *(uint16_t*)((uint8_t*)&s.t + k.off) = (uint16_t)v;
    return true;
  }
  struct { const char* k; uint8_t* p; uint8_t hi; } u8[] = {
    {"RETRIES", &s.retries, 5}, {"LOG", &s.logLevel, 3}, {"ECHO", &s.expectEcho, 1},
    {"AP_ALWAYS", &s.apAlways, 1}, {"AUTOKA", &s.autoKa, 1}};
  for (auto& k : u8) {
    if (strcmp(key, k.k)) continue;
    if (!parseU32(val, &v) || v > k.hi) { snprintf(err, errn, "%s: 0-%u", k.k, k.hi); return false; }
    *k.p = (uint8_t)v;
    return true;
  }
  if (!strcmp(key, "KA_MS")) {
    if (!parseU32(val, &v) || v < 300 || v > 4000) { snprintf(err, errn, "KA_MS 300-4000"); return false; }
    s.kaMs = (uint16_t)v; return true;
  }
  snprintf(err, errn, "clave desconocida %s (ver CONFIG)", key);
  return false;
}

void settingsShow(const Settings& s) {
  emit("INFO", "STA_SSID=%s STA_PASS=%s AP_SSID=%s AP_PASS=%s HOST=%s AP_ALWAYS=%u", s.staSsid,
       *s.staPass ? "****" : "", s.apSsid, *s.apPass ? "****" : "(abierta)", s.host, s.apAlways);
  emit("INFO", "ECU=%02X TESTER=%02X BAUD=%lu RETRIES=%u LOG=%u ECHO=%u AUTOKA=%u KA_MS=%u", s.ecu, s.tester,
       (unsigned long)s.baud, s.retries, s.logLevel, s.expectEcho, s.autoKa, s.kaMs);
  emit("INFO", "P1MAX=%u P2MAX=%u P2EXT=%u P3MIN=%u P4=%u W5=%u TINIL=%u TWUP=%u", s.t.p1max, s.t.p2max, s.t.p2ext,
       s.t.p3min, s.t.p4, s.t.w5, s.t.tinil, s.t.twup);
}
