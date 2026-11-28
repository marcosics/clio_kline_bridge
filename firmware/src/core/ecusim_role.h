// Papel "UCE simulada en la línea real" (banco de pruebas: un segundo micro hace de centralita 0x7A/0x26/0x28).
#pragma once
#include "hal.h"

class EcuSimRole {
 public:
  explicit EcuSimRole(Hal& h) : hal(h) {}
  void begin();
  void loop();

 private:
  Hal& hal;
  uint8_t buf[KBUF];
  int len = 0;
  uint32_t lastMs = 0;
  uint32_t answered = 0, bad = 0;
};
