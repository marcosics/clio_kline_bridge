#include "ecusim_role.h"
#include "config.h"
#ifndef NO_SIM
#include "ecusim.h"
#include "util.h"

void EcuSimRole::begin() {
  hal.kUart(DEFAULT_BAUD);
  emit("DBG", "UCE simulada en la linea K (7A inyeccion, 26 UCH, 28 ABS) - %s", hal.board());
}

void EcuSimRole::loop() {
  int c;
  while ((c = hal.kRead()) >= 0) {
    if (len && hal.ms() - lastMs > 20) len = 0;   // P1: hueco = trama nueva
    lastMs = hal.ms();
    if (len == 0 && c == 0x00) continue;         // pulso de wake-up leído como 0x00
    buf[len++] = (uint8_t)c;
    int need = kwpFrameLen(buf, len);
    if (len >= KBUF) { len = 0; continue; }
    if (need < 0 || len < need) continue;
    int fl = len;
    len = 0;
    if (!kwpChecksumOk(buf, fl)) { bad++; continue; }
    if (!(buf[0] & 0x80)) continue;
    uint8_t dst = buf[1], src = buf[2];
    if (!ecuSimPresent(dst)) continue;            // no es para nosotros (o es nuestro propio eco)
    static uint8_t a[KBUF], f[KBUF];
    int off = kwpDataOff(buf);
    int al = ecuSimAnswer(dst, buf + off, kwpDataLen(buf), a, hal.ms());
    if (!al) continue;
    int rl = kwpBuild(src, dst, a, al, f);
    hal.delayMs(30);                              // P2
    hal.kWrite(f, rl);
    uint32_t t = hal.ms();                        // descartar el eco de lo que acabamos de mandar
    int skip = rl;
    while (skip > 0 && hal.ms() - t < 50) {
      if (hal.kRead() >= 0) skip--;
      else hal.idle();
    }
    answered++;
    if (gLogLevel >= 1) {
      static char hx[KBUF * 3 + 8];
      bytesToHex(f, rl, hx, sizeof hx);
      emit("DBG", "%02X <- %02X: %s (%lu respondidas, %lu malas)", dst, src, hx, (unsigned long)answered,
           (unsigned long)bad);
    }
  }
}
#endif
