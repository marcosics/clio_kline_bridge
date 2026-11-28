// Ajustes guardados en la EEPROM (o en un archivo en el PC). Se cambian con SET clave valor + SAVE, o con WIFI.
#pragma once
#include "config.h"

struct Timing {
  uint16_t p1max = 20;    // ms máx. entre bytes de la UCE
  uint16_t p2max = 150;   // ms máx. hasta la respuesta (ISO: 50; con margen para la DDCR y el wifi)
  uint16_t p2ext = 5000;  // ms tras 7F xx 78 (respuesta pendiente)
  uint16_t p3min = 55;    // ms mín. entre la respuesta y la siguiente petición
  uint16_t p4 = 0;        // ms entre bytes del tester (0 = seguidos)
  uint16_t w5 = 300;      // ms de línea en reposo antes del init
  uint16_t tinil = 25;    // ms a nivel bajo del fast init
  uint16_t twup = 50;     // ms del patrón completo de wake-up (bajo + alto)
};

#if defined(ARDUINO_ARCH_AVR)   // el Uno no tiene wifi: textos mínimos para ahorrar RAM
  #define SSID_LEN 2
  #define PASS_LEN 2
  #define HOST_LEN 2
#else
  #define SSID_LEN 33
  #define PASS_LEN 65
  #define HOST_LEN 24
#endif

struct Settings {
  uint32_t magic;
  uint16_t version;
  char staSsid[SSID_LEN];
  char staPass[PASS_LEN];
  char apSsid[SSID_LEN];
  char apPass[PASS_LEN];
  char host[HOST_LEN];
  uint8_t ecu;
  uint8_t tester;
  uint32_t baud;
  Timing t;
  uint16_t kaMs;
  uint8_t retries;
  uint8_t logLevel;
  uint8_t expectEcho;     // 1: la línea devuelve el eco (L9637D, LM339, transistores)
  uint8_t apAlways;       // 1: la red propia siempre activa; 0: se apaga si hay wifi del móvil
  uint8_t autoKa;         // 1: keep-alive automático tras un init correcto
  uint32_t crc;
};

void settingsDefaults(Settings& s);
bool settingsLoad(Settings& s);              // false = por defecto (EEPROM vacía o corrupta)
bool settingsSave(const Settings& s);
bool settingsSet(Settings& s, const char* key, const char* val, char* err, size_t errn);
void settingsShow(const Settings& s);        // líneas INFO, claves ocultas
