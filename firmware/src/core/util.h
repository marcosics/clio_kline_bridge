// Utilidades KWP2000 (ISO 14230) y salida de texto. Sin dependencias de Arduino.
#pragma once
#include "hal.h"

uint8_t sum8(const uint8_t* b, size_t n);
int hexToBytes(const char* s, uint8_t* out, int max);          // ignora espacios; -1 si no es hex par
void bytesToHex(const uint8_t* b, int n, char* out, size_t outn);  // "AA BB CC"
bool kwpAllowed(const uint8_t* d, int n);                       // lista blanca de CLAUDE.md sec. 6

// Trama: [fmt][dst][src]([len])[datos][cs]. fmt = 0x80 | len (len <= 63) o 0x80 + byte de longitud.
int kwpBuild(uint8_t dst, uint8_t src, const uint8_t* d, int n, uint8_t* f);
int kwpFrameLen(const uint8_t* b, int have);   // longitud total esperada; -1 si aún no se sabe
int kwpDataOff(const uint8_t* b);
int kwpDataLen(const uint8_t* b);
bool kwpChecksumOk(const uint8_t* b, int n);

// Salida: "<PFX> <micros> <texto>". Prefijos: OK, ERR (solo como fin de comando), TX, RX, ECHO, RAW, DBG, EVT, INFO.
void outInit(Hal* h);
#if defined(ARDUINO_ARCH_AVR)   // Uno: los textos de formato van a la flash (PROGMEM), no a los 2 KB de RAM
  #include <avr/pgmspace.h>
  #include <stdio.h>
  void emitP(const char* pfx, const char* fmtP, ...);
  #define emit(pfx, fmt, ...) emitP(pfx, PSTR(fmt), ##__VA_ARGS__)
  #define snprintf(b, n, fmt, ...) snprintf_P(b, n, PSTR(fmt), ##__VA_ARGS__)
#else
  void emit(const char* pfx, const char* fmt, ...);
#endif
void logRing(void (*cb)(const char* line, void* ctx), void* ctx);
extern uint8_t gLogLevel;   // 0 errores, 1 normal, 2 + eco, 3 todo

// Texto
void upcase(char* s);
char* trim(char* s);
char* nextTok(char** s);    // siguiente palabra (modifica la cadena)
bool parseU32(const char* s, uint32_t* v, int base = 10);
