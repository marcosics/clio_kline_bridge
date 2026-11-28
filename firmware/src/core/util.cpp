#include "util.h"
#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

uint8_t gLogLevel = 1;
static Hal* gHal = nullptr;
#if LOG_LINES > 0
static char ring[LOG_LINES][LOG_LINE_LEN];
static uint16_t ringHead = 0, ringCount = 0;
#endif

uint8_t sum8(const uint8_t* b, size_t n) {
  uint8_t s = 0;
  for (size_t i = 0; i < n; i++) s += b[i];
  return s;
}

int hexToBytes(const char* s, uint8_t* out, int max) {
  int n = 0, half = -1;
  for (; *s; s++) {
    char c = *s;
    if (c == ' ' || c == ':' || c == '-' || c == '\t') continue;
    int v = isdigit((unsigned char)c) ? c - '0' : (c >= 'a' && c <= 'f') ? c - 'a' + 10 : (c >= 'A' && c <= 'F') ? c - 'A' + 10 : -1;
    if (v < 0) return -1;
    if (half < 0) half = v;
    else {
      if (n >= max) return -1;
      out[n++] = (uint8_t)(half << 4 | v);
      half = -1;
    }
  }
  return half >= 0 ? -1 : n;
}

void bytesToHex(const uint8_t* b, int n, char* out, size_t outn) {
  static const char* H = "0123456789ABCDEF";
  size_t o = 0;
  for (int i = 0; i < n && o + 3 < outn; i++) {
    if (i) out[o++] = ' ';
    out[o++] = H[b[i] >> 4];
    out[o++] = H[b[i] & 15];
  }
  if (outn) out[o < outn ? o : outn - 1] = 0;
}

bool kwpAllowed(const uint8_t* d, int n) {
  if (n < 1) return false;
  switch (d[0]) {
    case 0x81:                       // StartCommunication (lo usa el init)
    case 0x3E:                       // TesterPresent
    case 0x21:                       // ReadDataByLocalIdentifier
    case 0x17: case 0x18:            // lectura de averías
    case 0x1A:                       // ReadEcuIdentification
      return true;
    case 0x10: return n >= 2 && d[1] == 0xC0;   // solo la sesión Renault de diagnóstico
    default: return false;          // 2E, 3B, 14, 27, 31, 11, 34-37, 10 85... bloqueados
  }
}

int kwpBuild(uint8_t dst, uint8_t src, const uint8_t* d, int n, uint8_t* f) {
  int o;
  if (n <= 63) { f[0] = 0x80 | n; f[1] = dst; f[2] = src; o = 3; }
  else { f[0] = 0x80; f[1] = dst; f[2] = src; f[3] = (uint8_t)n; o = 4; }
  memcpy(f + o, d, n);
  f[o + n] = sum8(f, o + n);
  return o + n + 1;
}

int kwpDataOff(const uint8_t* b) { return ((b[0] & 0x80) ? 3 : 1) + ((b[0] & 0x3F) == 0 ? 1 : 0); }

int kwpDataLen(const uint8_t* b) {
  int len = b[0] & 0x3F;
  return len ? len : b[(b[0] & 0x80) ? 3 : 1];
}

int kwpFrameLen(const uint8_t* b, int have) {
  if (have < 1) return -1;
  int hdr = (b[0] & 0x80) ? 3 : 1, len = b[0] & 0x3F;
  if (len == 0) {
    if (have <= hdr) return -1;
    len = b[hdr];
    hdr++;
  }
  return hdr + len + 1;
}

bool kwpChecksumOk(const uint8_t* b, int n) { return n > 1 && sum8(b, n - 1) == b[n - 1]; }

// ---------------------------------------------------------------- salida
void outInit(Hal* h) { gHal = h; }

#if defined(ARDUINO_ARCH_AVR)
void emitP(const char* pfx, const char* fmt, ...) {
#else
void emit(const char* pfx, const char* fmt, ...) {
#endif
  if (!gHal) return;
  static char line[CMD_LINE_MAX];   // estática: la pila del ESP8266 es pequeña
  int o = snprintf(line, sizeof line, "%s %lu ", pfx, (unsigned long)gHal->us());
  va_list ap;
  va_start(ap, fmt);
#if defined(ARDUINO_ARCH_AVR)
  vsnprintf_P(line + o, sizeof line - o, fmt, ap);
#else
  vsnprintf(line + o, sizeof line - o, fmt, ap);
#endif
  va_end(ap);
  gHal->out(line);
#if LOG_LINES > 0
  strncpy(ring[ringHead], line, LOG_LINE_LEN - 1);
  ring[ringHead][LOG_LINE_LEN - 1] = 0;
  ringHead = (ringHead + 1) % LOG_LINES;
  if (ringCount < LOG_LINES) ringCount++;
#endif
}

void logRing(void (*cb)(const char*, void*), void* ctx) {
#if LOG_LINES > 0
  for (uint16_t i = 0; i < ringCount; i++) cb(ring[(ringHead + LOG_LINES - ringCount + i) % LOG_LINES], ctx);
#else
  (void)cb; (void)ctx;
#endif
}

// ---------------------------------------------------------------- texto
void upcase(char* s) {
  for (; *s; s++) *s = (char)toupper((unsigned char)*s);
}

char* trim(char* s) {
  while (*s && isspace((unsigned char)*s)) s++;
  char* e = s + strlen(s);
  while (e > s && isspace((unsigned char)e[-1])) *--e = 0;
  return s;
}

char* nextTok(char** s) {
  char* p = *s;
  while (*p == ' ') p++;
  if (!*p) { *s = p; return nullptr; }
  char* t = p;
  while (*p && *p != ' ') p++;
  if (*p) *p++ = 0;
  *s = p;
  return t;
}

bool parseU32(const char* s, uint32_t* v, int base) {
  if (!s || !*s) return false;
  char* e;
  unsigned long x = strtoul(s, &e, base);
  if (*e) return false;
  *v = (uint32_t)x;
  return true;
}
