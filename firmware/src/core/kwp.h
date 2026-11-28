// Motor KWP2000 sobre línea K (ISO 14230): init rápido y a 5 baudios, peticiones con eco, tiempos P1-P4,
// respuesta pendiente (7F xx 78), reintentos, keep-alive, sniffer y pruebas del hardware. Solo lectura.
#pragma once
#include "hal.h"
#include "settings.h"

enum class Link : uint8_t { Idle, Up, Lost };
enum class KRes : uint8_t { Ok, Timeout, Checksum, Incomplete, Blocked, NoLink, BadEcho };

struct KStats {
  uint32_t tx, rx, neg, timeouts, checksum, incomplete, echoErr, noEcho, inits, initFail, kaFail, retries, junk;
};

class Kwp {
 public:
  explicit Kwp(Hal& h, Settings& s) : hal(h), cfg(s) {}

  // estado
  Link link = Link::Idle;
  bool sim = false;        // UCE simulada sin línea
  bool sniff = false;      // escucha pasiva
  bool ka = false;         // keep-alive activo
  uint8_t ecu = DEFAULT_ECU;
  uint8_t kb1 = 0, kb2 = 0;
  KStats st = {};
  uint32_t lastTxMs = 0, lastRxMs = 0, upSinceMs = 0;

  // última respuesta
  uint8_t rsp[KBUF];
  int rspLen = 0, rspOff = 0, rspDataLen = 0;
  const uint8_t* data() const { return rsp + rspOff; }

  void begin();
  bool fastInit(char* why, size_t whyn);
  bool slowInit(char* why, size_t whyn);
  KRes request(const uint8_t* d, int n, bool quiet = false);
  void poll();                                   // keep-alive y sniffer; llamar en cada vuelta del loop

  // pruebas del hardware (sin UCE)
  bool testEcho(int n, char* msg, size_t mn);    // manda bytes y comprueba que vuelven por el RX
  bool testLine(char* msg, size_t mn);           // niveles: K en reposo y TX → RX
  const char* linkName() const { return link == Link::Up ? "UP" : link == Link::Lost ? "LOST" : "IDLE"; }

 private:
  Hal& hal;
  Settings& cfg;
  uint8_t kaFails = 0;
  uint8_t snBuf[KBUF];
  int snLen = 0;
  uint32_t snLastUs = 0;

  KRes once(const uint8_t* d, int n, bool quiet);
  int readFrame(uint8_t* b, int max, uint32_t firstMs, int* got);
  void drain();
  void waitP3();
  void sniffPoll();
  int readByte(uint32_t timeoutMs);
  void sendRaw(const uint8_t* b, int n);
};

const char* kresName(KRes r);
