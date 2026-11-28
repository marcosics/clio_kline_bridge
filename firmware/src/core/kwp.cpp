#include "kwp.h"
#include <stdio.h>
#include <string.h>
#include "ecusim.h"
#include "util.h"

static char HX[HEX_LEN];   // hex de la trama en curso (estático: pila pequeña en el ESP8266)
char gDetail[HEX_LEN];     // detalle del último error (bytes recibidos, etc.)

const char* kresName(KRes r) {
  switch (r) {
    case KRes::Ok: return "OK";
    case KRes::Timeout: return "TIMEOUT";
    case KRes::Checksum: return "CHECKSUM";
    case KRes::Incomplete: return "INCOMPLETE";
    case KRes::Blocked: return "BLOCKED";
    case KRes::NoLink: return "NOLINK";
    case KRes::BadEcho: return "NOECHO";
  }
  return "?";
}

void Kwp::begin() {
  ecu = cfg.ecu;
  hal.kUart(cfg.baud);
}

int Kwp::readByte(uint32_t timeoutMs) {
  uint32_t t0 = hal.ms();
  for (;;) {
    int c = hal.kRead();
    if (c >= 0) return c;
    if (hal.ms() - t0 >= timeoutMs) return -1;
    hal.idle();
  }
}

void Kwp::sendRaw(const uint8_t* b, int n) {
  if (!cfg.t.p4) {
    hal.kWrite(b, n);
    return;
  }
  for (int i = 0; i < n; i++) {
    hal.kWrite(b + i, 1);
    hal.delayMs(cfg.t.p4);
  }
}

void Kwp::drain() {
  while (hal.kRead() >= 0) st.junk++;
}

void Kwp::waitP3() {
  uint32_t last = lastRxMs > lastTxMs ? lastRxMs : lastTxMs;
  while (hal.ms() - last < cfg.t.p3min) hal.idle();
}

// Lee una trama. >0 longitud completa; 0 nada en firstMs; -1 incompleta o demasiado larga (*got = bytes leídos).
int Kwp::readFrame(uint8_t* b, int max, uint32_t firstMs, int* got) {
  int i = 0;
  uint32_t t = hal.ms();
  for (;;) {
    int c = hal.kRead();
    if (c >= 0) {
      t = hal.ms();
      if (i == 0 && c == 0x00) continue;   // restos del pulso de wake-up / break
      b[i++] = (uint8_t)c;
      int need = kwpFrameLen(b, i);
      if (need > max || (need < 0 && i >= max)) { *got = i; return -1; }
      if (need > 0 && i >= need) { *got = i; return i; }
      continue;
    }
    uint32_t lim = i ? (uint32_t)cfg.t.p1max + 5 : firstMs;
    if (hal.ms() - t >= lim) { *got = i; return i ? -1 : 0; }
    hal.idle();
  }
}

KRes Kwp::once(const uint8_t* d, int n, bool quiet) {
  static uint8_t f[KBUF];
  int fl = kwpBuild(ecu, cfg.tester, d, n, f);
  waitP3();
  drain();
  if (!quiet) {
    bytesToHex(f, fl, HX, sizeof HX);
    emit("TX", "%s", HX);
  }
  sendRaw(f, fl);
  lastTxMs = hal.ms();
  st.tx++;

  if (cfg.expectEcho) {   // half-duplex: lo enviado vuelve por el RX
    static uint8_t eb[KBUF];
    int e = 0;
    bool bad = false;
    for (int i = 0; i < fl; i++) {
      int c = readByte(i == 0 ? 30 : (uint32_t)cfg.t.p1max + 5 + cfg.t.p4);
      if (c < 0) break;
      eb[e++] = (uint8_t)c;
      if (c != f[i]) bad = true;
    }
    if (e == 0) {
      st.noEcho++;
      snprintf(gDetail, sizeof gDetail, "no vuelve el eco: el TX no llega a la K o el RX no lee (prueba TEST LINE)");
      return KRes::BadEcho;
    }
    if (e < fl || bad) {
      st.echoErr++;
      bytesToHex(eb, e, HX, sizeof HX);
      emit("EVT", "eco distinto (%d/%d bytes): %s - colision con otro tester o transceptor mal", e, fl, HX);
    } else if (gLogLevel >= 2) {
      bytesToHex(eb, e, HX, sizeof HX);
      emit("ECHO", "%s", HX);
    }
  }

  uint32_t deadline = hal.ms() + cfg.t.p2max;
  for (;;) {
    int32_t left = (int32_t)(deadline - hal.ms());
    if (left < 1) left = 1;
    int got = 0;
    int rl = readFrame(rsp, KBUF, (uint32_t)left, &got);
    if (rl == 0) {
      st.timeouts++;
      snprintf(gDetail, sizeof gDetail, "sin respuesta en %u ms (P2MAX)", cfg.t.p2max);
      return KRes::Timeout;
    }
    if (rl < 0) {
      st.incomplete++;
      bytesToHex(rsp, got, gDetail, sizeof gDetail);
      return KRes::Incomplete;
    }
    if (!kwpChecksumOk(rsp, rl)) {
      st.checksum++;
      bytesToHex(rsp, rl, gDetail, sizeof gDetail);
      return KRes::Checksum;
    }
    if ((rsp[0] & 0x80) && (rsp[1] != cfg.tester || rsp[2] != ecu)) {   // trama de otra conversación
      st.junk++;
      bytesToHex(rsp, rl, HX, sizeof HX);
      emit("EVT", "trama ignorada (no es para %02X desde %02X): %s", cfg.tester, ecu, HX);
      continue;
    }
    rspLen = rl;
    rspOff = kwpDataOff(rsp);
    rspDataLen = kwpDataLen(rsp);
    lastRxMs = hal.ms();
    st.rx++;
    if (!quiet) {
      bytesToHex(rsp, rl, HX, sizeof HX);
      emit("RX", "%s", HX);
    }
    if (rsp[rspOff] == 0x7F && rspDataLen >= 3) {
      if (rsp[rspOff + 2] == 0x78) {   // respuesta pendiente: seguir esperando
        deadline = hal.ms() + cfg.t.p2ext;
        continue;
      }
      st.neg++;
    }
    return KRes::Ok;
  }
}

KRes Kwp::request(const uint8_t* d, int n, bool quiet) {
  if (!kwpAllowed(d, n)) return KRes::Blocked;
  gDetail[0] = 0;
#ifndef NO_SIM
  if (sim) {   // UCE simulada sin línea: misma salida que con la línea
    static uint8_t a[KBUF], f[KBUF];
    int fl = kwpBuild(ecu, cfg.tester, d, n, f);
    if (!quiet) { bytesToHex(f, fl, HX, sizeof HX); emit("TX", "%s", HX); }
    lastTxMs = hal.ms();
    st.tx++;
    int al = ecuSimAnswer(ecu, d, n, a, hal.ms());
    if (!al) { st.timeouts++; snprintf(gDetail, sizeof gDetail, "UCE %02X no existe en el simulador", ecu); return KRes::Timeout; }
    rspLen = kwpBuild(cfg.tester, ecu, a, al, rsp);
    rspOff = kwpDataOff(rsp);
    rspDataLen = al;
    lastRxMs = hal.ms();
    st.rx++;
    if (!quiet) { bytesToHex(rsp, rspLen, HX, sizeof HX); emit("RX", "%s", HX); }
    return KRes::Ok;
  }
#endif
  KRes r = KRes::Timeout;
  for (uint8_t a = 0; a <= cfg.retries; a++) {
    if (a) {
      st.retries++;
      if (!quiet) emit("EVT", "reintento %u: %s %s", a, kresName(r), gDetail);
    }
    r = once(d, n, quiet);
    if (r == KRes::Ok || r == KRes::BadEcho) break;
  }
  if (r == KRes::Ok && link == Link::Lost) link = Link::Up;
  return r;
}

static void emitKeybytes(uint8_t ecu, uint8_t kb1, uint8_t kb2, const char* how) {
  emit("DBG", "init %s %02X OK: keybytes %02X %02X (%s)", how, ecu, kb1, kb2,
       (kb1 & 0x04) ? "cabecera con direcciones" : "cabecera sin direcciones");
}

bool Kwp::fastInit(char* why, size_t whyn) {
  st.inits++;
  ka = false;
  link = Link::Idle;
#ifdef NO_SIM
  if (sim) { snprintf(why, whyn, "esta placa no tiene simulador"); return false; }
#else
  if (sim) {
    if (!ecuSimPresent(ecu)) { snprintf(why, whyn, "UCE %02X no contesta (simulador)", ecu); st.initFail++; return false; }
    uint8_t sc = 0x81;
    request(&sc, 1);
    kb1 = 0xEF; kb2 = 0x8F;
  } else
#endif
  {
    hal.kGpio();
    hal.kTx(true);
    hal.delayMs(cfg.t.w5);                       // W5: línea en reposo
    if (hal.kRxLevel() == 0) {
      hal.kUart(cfg.baud);
      st.initFail++;
      snprintf(why, whyn, "la K esta en bajo antes del init: sin 12 V en el pull-up, corto, o otro tester hablando");
      return false;
    }
    hal.kTx(false);
    hal.delayMs(cfg.t.tinil);                    // TiniL 25 ms abajo
    hal.kTx(true);
    hal.delayMs(cfg.t.twup - cfg.t.tinil);       // resto de TWup arriba
    hal.kUart(cfg.baud);
    lastRxMs = lastTxMs = 0;
    uint8_t sc = 0x81;                           // StartCommunication
    gDetail[0] = 0;
    uint16_t p3 = cfg.t.p3min;
    cfg.t.p3min = 0;                             // justo tras el wake-up, sin esperar P3
    KRes r = once(&sc, 1, false);
    cfg.t.p3min = p3;
    if (r != KRes::Ok || rspDataLen < 3 || rsp[rspOff] != 0xC1) {
      st.initFail++;
      if (r == KRes::Ok)
        snprintf(why, whyn, "respuesta inesperada al StartCommunication");
      else
        snprintf(why, whyn, "%s %s%s", kresName(r), gDetail,
                 r == KRes::Timeout ? " - contacto puesto? direccion correcta? prueba INIT SLOW" : "");
      return false;
    }
    kb1 = rsp[rspOff + 1];
    kb2 = rsp[rspOff + 2];
  }
  link = Link::Up;
  upSinceMs = hal.ms();
  kaFails = 0;
  ka = cfg.autoKa;
  emitKeybytes(ecu, kb1, kb2, "rapido");
  return true;
}

bool Kwp::slowInit(char* why, size_t whyn) {
  st.inits++;
  ka = false;
  link = Link::Idle;
  if (sim) return fastInit(why, whyn);
  hal.kGpio();
  hal.kTx(true);
  hal.delayMs(cfg.t.w5);
  if (hal.kRxLevel() == 0) {
    hal.kUart(cfg.baud);
    st.initFail++;
    snprintf(why, whyn, "la K esta en bajo antes del init");
    return false;
  }
  emit("DBG", "init a 5 baudios a %02X (2 s)...", ecu);
  hal.kTx(false);                               // bit de start
  hal.delayMs(200);
  for (int b = 0; b < 8; b++) {                 // 8 bits, el menos significativo primero
    hal.kTx((ecu >> b) & 1);
    hal.delayMs(200);
  }
  hal.kTx(true);                                // bit de stop
  hal.kUart(cfg.baud);
  drain();
  int sync = readByte(200 + 300 + 100);         // stop + W1 (20-300 ms) + margen
  if (sync != 0x55) {
    st.initFail++;
    if (sync < 0) snprintf(why, whyn, "sin byte de sincronia 0x55 (la UCE no despierta a 5 baudios)");
    else snprintf(why, whyn, "sincronia %02X en vez de 55: otra velocidad? (BAUD 9600)", sync);
    return false;
  }
  int k1 = readByte(60), k2 = readByte(60);     // W2, W3
  if (k1 < 0 || k2 < 0) {
    st.initFail++;
    snprintf(why, whyn, "faltan los keybytes tras 0x55");
    return false;
  }
  hal.delayMs(30);                              // W4: 25-50 ms
  uint8_t inv = (uint8_t)~k2;
  sendRaw(&inv, 1);
  if (cfg.expectEcho) readByte(30);
  int a = readByte(100);
  if (a < 0 || (uint8_t)a != (uint8_t)~ecu) {
    st.initFail++;
    if (a < 0) snprintf(why, whyn, "la UCE no devuelve la direccion invertida");
    else snprintf(why, whyn, "direccion invertida %02X (esperaba %02X)", a, (uint8_t)~ecu);
    return false;
  }
  kb1 = (uint8_t)k1;
  kb2 = (uint8_t)k2;
  lastRxMs = hal.ms();
  link = Link::Up;
  upSinceMs = hal.ms();
  kaFails = 0;
  ka = cfg.autoKa;
  emitKeybytes(ecu, kb1, kb2, "5 baudios");
  return true;
}

void Kwp::sniffPoll() {
  uint32_t now = hal.us();
  int c;
  while ((c = hal.kRead()) >= 0) {
    if (snLen && (now - snLastUs > 5000 || snLen >= KBUF)) {   // hueco > 5 ms = fin de trama
      bytesToHex(snBuf, snLen, HX, sizeof HX);
      emit("RAW", "%s cs=%s", HX, kwpChecksumOk(snBuf, snLen) ? "ok" : "mal");
      snLen = 0;
    }
    snBuf[snLen++] = (uint8_t)c;
    snLastUs = now = hal.us();
  }
  if (snLen && hal.us() - snLastUs > 5000) {
    bytesToHex(snBuf, snLen, HX, sizeof HX);
    emit("RAW", "%s cs=%s", HX, kwpChecksumOk(snBuf, snLen) ? "ok" : "mal");
    snLen = 0;
  }
}

void Kwp::poll() {
  if (sniff) {
    sniffPoll();
    return;
  }
  if (link != Link::Up || !ka || hal.ms() - lastTxMs < cfg.kaMs) return;
  uint8_t k = 0x3E;
  KRes r = request(&k, 1, gLogLevel < 3);
  if (r == KRes::Ok && rsp[rspOff] == 0x7E) {
    kaFails = 0;
    return;
  }
  kaFails++;
  st.kaFail++;
  emit("EVT", "keep-alive sin respuesta (%u/3): %s %s", kaFails, kresName(r), gDetail);
  if (kaFails >= 3) {
    link = Link::Lost;
    ka = false;
    emit("EVT", "LINK LOST %02X: la UCE no contesta (contacto quitado?). Hace falta INIT de nuevo", ecu);
  }
}

bool Kwp::testEcho(int n, char* msg, size_t mn) {
  if (sim) { snprintf(msg, mn, "en modo SIM no hay linea"); return false; }
  static const uint8_t pat[] = {0x55, 0xAA, 0x00, 0xFF, 0x0F, 0xF0, 0x7A, 0xF1, 0x81, 0x3E, 0x33, 0xCC, 0x01, 0x80, 0x21, 0xA1};
  if (n < 1) n = 8;
  if (n > (int)sizeof pat) n = sizeof pat;
  drain();
  int okc = 0, got = 0;
  for (int i = 0; i < n; i++) {
    hal.kWrite(pat + i, 1);
    int c = readByte(30);
    if (c >= 0) got++;
    if (c == pat[i]) okc++;
  }
  lastTxMs = hal.ms();
  if (okc == n) { snprintf(msg, mn, "%d/%d bytes vuelven bien: TX, K y RX correctos", okc, n); return true; }
  if (got == 0) snprintf(msg, mn, "0/%d: no vuelve nada. TX no llega a la K o RX no lee (TEST LINE)", n);
  else snprintf(msg, mn, "%d/%d bien, %d recibidos: ruido, baudios o nivel de umbral (R1/R2/R3)", okc, n, got);
  return false;
}

bool Kwp::testLine(char* msg, size_t mn) {
  if (sim) { snprintf(msg, mn, "en modo SIM no hay linea"); return false; }
  hal.kGpio();
  hal.kTx(true);
  hal.delayMs(30);
  int idle = hal.kRxLevel();
  hal.kTx(false);
  hal.delayMs(3);
  int low = hal.kRxLevel();
  hal.kTx(true);
  hal.delayMs(3);
  int back = hal.kRxLevel();
  hal.kUart(cfg.baud);
  drain();
  bool ok = idle == 1 && low == 0 && back == 1;
  if (idle < 0) snprintf(msg, mn, "esta placa no puede leer el RX como GPIO; usa TEST ECHO");
  else if (ok) snprintf(msg, mn, "reposo=1 tx0->0 tx1->1: K alta en reposo y el TX la baja. Hardware bien");
  else if (idle == 0) snprintf(msg, mn, "reposo=0: K en bajo. Falta 12 V en R10, corto a masa, LM339 sin 3,3 V o R4 suelta");
  else if (low == 1) snprintf(msg, mn, "reposo=1 tx0->1: el TX no baja la K. Revisa GPIO2 (puerta), D2, R7, comparadores TX y R10");
  else snprintf(msg, mn, "reposo=%d tx0->%d tx1->%d: la K no vuelve a alto (pull-up R10 o salida pegada)", idle, low, back);
  return ok;
}
