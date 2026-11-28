#include "ecusim.h"
#ifndef NO_SIM
#include <string.h>

bool ecuSimPresent(uint8_t ecu) { return ecu == 0x7A || ecu == 0x26 || ecu == 0x28; }

static void drive(uint32_t ms, uint16_t* rpm, uint8_t* kmh, uint8_t* temp, uint8_t* brake) {
  uint32_t ph = (ms / 1000) % 60;
  int v = ph < 8 ? 0 : ph < 40 ? (int)(ph - 8) * 3 : 90 - (int)(ph - 40) * 5;
  if (v > 90) v = 90;
  if (v < 0) v = 0;
  static const uint8_t ratio[5] = {130, 75, 50, 38, 31};
  int gear = v < 15 ? 0 : v < 30 ? 1 : v < 50 ? 2 : v < 70 ? 3 : 4;
  *rpm = v == 0 ? 820 + (ms / 100) % 20 : (uint16_t)(v * ratio[gear] + 900);
  *kmh = (uint8_t)v;
  uint32_t t = 20 + ms / 4000;
  *temp = (uint8_t)(t > 88 ? 88 : t);
  *brake = (ph >= 40 && ph < 52) ? 1 : 0;
}

int ecuSimAnswer(uint8_t ecu, const uint8_t* q, int n, uint8_t* r, uint32_t ms) {
  if (!ecuSimPresent(ecu) || n < 1) return 0;
  uint16_t rpm; uint8_t kmh, temp, brake;
  drive(ms, &rpm, &kmh, &temp, &brake);
  switch (q[0]) {
    case 0x81: r[0] = 0xC1; r[1] = 0xEF; r[2] = 0x8F; return 3;
    case 0x10:
      if (n > 1 && q[1] == 0xC0) { r[0] = 0x50; r[1] = 0xC0; return 2; }
      break;
    case 0x3E: r[0] = 0x7E; return 1;
    case 0x17: case 0x18:   // una avería ficticia
      r[0] = q[0] + 0x40; r[1] = 1; r[2] = 0x01; r[3] = 0x23; r[4] = 0xA0; return 5;
    case 0x21: {
      uint8_t lid = n > 1 ? q[1] : 0;
      if (ecu == 0x28) {
        if (lid != 0xA0) break;
        r[0] = 0x61; r[1] = lid;   // ABS: 4 ruedas, km/h x 100, little endian
        for (int i = 0; i < 4; i++) { uint16_t w = kmh * 100 + i * 7; r[2 + i * 2] = w & 0xFF; r[3 + i * 2] = w >> 8; }
        return 10;
      }
      if (lid != 0x80 && lid != 0xA0 && lid != 0xA1 && lid != 0xA2) break;
      r[0] = 0x61; r[1] = lid;
      for (int i = 2; i < 26; i++) r[i] = (uint8_t)(lid * 7 + i * 13);
      if (lid == 0xA1) { r[2] = rpm & 0xFF; r[3] = rpm >> 8; r[6] = temp + 40; }   // 16 bits little endian
      if (lid == 0xA2) { r[5] = kmh; r[7] = 0x10 | brake; }
      if (lid == 0x80) memcpy(r + 2, ecu == 0x26 ? "SIMUCH8200001" : "SIM8200212348", 13);
      return 26;
    }
    case 0x1A:
      r[0] = 0x5A; r[1] = n > 1 ? q[1] : 0x80;
      memcpy(r + 2, "SIM-ECU", 7);
      return 9;
  }
  r[0] = 0x7F; r[1] = q[0]; r[2] = q[0] == 0x21 ? 0x12 : 0x11;   // subfunción no soportada / servicio no soportado
  return 3;
}
#endif
