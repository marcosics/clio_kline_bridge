// Tamaños y valores por defecto del puente clio-kline. Núcleo portátil: sin Arduino.h (también compila en el PC).
#pragma once
#include <stdint.h>
#include <stddef.h>

#define FW_VERSION "2.0.0"

#if defined(ARDUINO_ARCH_AVR)
  #define KBUF 48          // Uno: 2 KB de RAM (tramas de hasta 43 bytes de datos: las de la DDCR caben)
  #define LINE_MAX 100
  #define WHY_LEN 90
  #define HEX_LEN 80        // hex de tramas en el log (se recorta)
  #define NO_SIM 1          // sin UCE simulada en el Uno (no cabe)
  #define LOG_LINES 0
  #define LOG_LINE_LEN 1
#else
  #define KBUF 264         // trama KWP2000 máxima: 4 de cabecera + 255 datos + checksum
  #define LINE_MAX 900      // cabe una trama de 260 bytes en hex
  #define LOG_LINES 40     // últimas líneas para LOGDUMP y la página web del ESP
  #define LOG_LINE_LEN 160
  #define WHY_LEN 160
  #define HEX_LEN (KBUF * 3 + 8)
#endif

#define TESTER_ADDR 0xF1
#define DEFAULT_ECU 0x7A
#define DEFAULT_BAUD 10400UL

#ifndef WIFI_SSID
  #define WIFI_SSID "CLIO-KLINE"
#endif
#ifndef WIFI_PASS
  #define WIFI_PASS "clio1234"
#endif
#ifndef STA_SSID
  #define STA_SSID ""
#endif
#ifndef STA_PASS
  #define STA_PASS ""
#endif
#ifndef HOSTNAME
  #define HOSTNAME "clio-kline"
#endif
