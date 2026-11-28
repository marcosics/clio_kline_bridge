// Puente linea K (ISO 14230, 10400 8N1) <-> comandos de texto por USB y/o TCP :23.
// Protocolo y seguridad: CLAUDE.md secciones 6 y 8. Solo servicios de lectura; el resto -> ERR BLOCKED.
// Con -DROLE_ECUSIM el micro hace de UCE 0x7A simulada en la linea K (banco de pruebas).
#include <Arduino.h>

#if defined(ESP32)
  #include <WiFi.h>
  #include <ESPmDNS.h>
  #include <WiFiUdp.h>
  #define HAS_WIFI 1
  #define CMD_SERIAL 1
  #define BOARD "esp32"
  HardwareSerial &K = Serial2;
  const int K_RX = 16, K_TX = 17;
  void kBegin() { K.begin(10400, SERIAL_8N1, K_RX, K_TX); }
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <ESP8266mDNS.h>
  #include <WiFiUdp.h>
  #define HAS_WIFI 1
  #define CMD_SERIAL 0  // el unico UART es la linea K: comandos solo por Wi-Fi
  HardwareSerial &K = Serial;
  #ifdef BOARD_D1MINI
    #define BOARD "d1mini"
    const int K_TX = 15;
    void kBegin() { K.begin(10400); K.swap(); }  // RX13/TX15
  #else
    #define BOARD "esp01"
    const int K_TX = 1;
    void kBegin() { K.begin(10400); }
  #endif
#else
  #include <AltSoftSerial.h>
  #define HAS_WIFI 0
  #define CMD_SERIAL 1
  #define BOARD "uno"
  AltSoftSerial K;  // RX 8, TX 9
  const int K_TX = 9;
  void kBegin() { K.begin(10400); }
#endif

#ifndef WIFI_SSID
  #define WIFI_SSID "CLIO-KLINE"
#endif
#ifndef WIFI_PASS
  #define WIFI_PASS "clio1234"  // AP local del coche; cambiar con -DWIFI_PASS=\"...\"
#endif

#if HAS_WIFI
WiFiServer server(23);
WiFiUDP udp;           // descubrimiento: responde "CLIO <ip> <placa>" a "CLIO?" en el puerto 4210
bool mdnsOn = false;
WiFiClient client;
String tbuf;
#endif
String sbuf;

uint8_t ecu = 0x7A;
bool sim = false, sniff = false, ka = false;
uint32_t kaMs = 1500, lastTx = 0;
uint8_t rsp[80];
int rspLen = 0, rspOff = 0;

void emit(const char *pfx, const String &s) {
  String line = String(pfx) + " " + String((unsigned long)micros()) + " " + s;
#if CMD_SERIAL
  Serial.println(line);
#endif
#if HAS_WIFI
  if (client && client.connected()) client.println(line);
#endif
}

String hex(const uint8_t *b, int n) {
  String s;
  char t[4];
  for (int i = 0; i < n; i++) {
    sprintf(t, i ? " %02X" : "%02X", b[i]);
    s += t;
  }
  return s;
}

int parseHex(const String &s, uint8_t *out, int max) {
  String h;
  for (unsigned i = 0; i < s.length(); i++)
    if (isxdigit(s[i])) h += s[i];
  if (h.length() % 2) return -1;
  int n = 0;
  for (unsigned i = 0; i < h.length() && n < max; i += 2) out[n++] = strtoul(h.substring(i, i + 2).c_str(), 0, 16);
  return n;
}

// Lista blanca: 81 StartComm, 10C0, 3E, 21, 17, 18, 1A. Todo lo demas (2E, 3B, 14, 27, 31, 11, 34-37, 1085...) bloqueado.
bool allowed(const uint8_t *d, int n) {
  switch (d[0]) {
    case 0x81: case 0x3E: case 0x21: case 0x17: case 0x18: case 0x1A: return true;
    case 0x10: return n >= 2 && d[1] == 0xC0;
    default: return false;
  }
}

int buildFrame(uint8_t dst, uint8_t src, const uint8_t *d, int n, uint8_t *f) {
  f[0] = 0x80 | n;
  f[1] = dst;
  f[2] = src;
  memcpy(f + 3, d, n);
  uint8_t cs = 0;
  for (int i = 0; i < n + 3; i++) cs += f[i];
  f[n + 3] = cs;
  return n + 4;
}

int dataOff(const uint8_t *b) { return ((b[0] & 0x80) ? 3 : 1) + ((b[0] & 0x3F) == 0 ? 1 : 0); }

int frameLen(const uint8_t *b, int i) {
  int hdr = (b[0] & 0x80) ? 3 : 1, len = b[0] & 0x3F;
  if (len == 0) {
    if (i <= hdr) return -1;
    len = b[hdr];
    hdr++;
  }
  return hdr + len + 1;
}

bool csOk(const uint8_t *b, int n) {
  uint8_t s = 0;
  for (int i = 0; i < n - 1; i++) s += b[i];
  return n > 1 && s == b[n - 1];
}

// Lee una trama completa. 0 = nada; negativo = trama incompleta (-bytes leidos).
int readFrame(uint8_t *b, int max, uint32_t firstMs) {
  int i = 0;
  uint32_t t = millis();
  while (true) {
    if (K.available()) {
      uint8_t c = K.read();
      t = millis();
      if (i == 0 && c == 0) continue;  // restos del pulso de wake-up
      b[i++] = c;
      int need = frameLen(b, i);
      if ((need > 0 && i >= need) || i >= max) return i;
    } else if (millis() - t > (i ? 25UL : firstMs)) {
      return -i;  // P1max 20 ms entre bytes
    }
    yield();
  }
}

// UCE simulada: misma logica para SIM ON (sin linea) y para ROLE_ECUSIM (en la linea).
int simAnswer(const uint8_t *q, int n, uint8_t *r) {
  switch (q[0]) {
    case 0x81: r[0] = 0xC1; r[1] = 0xEF; r[2] = 0x8F; return 3;
    case 0x10: r[0] = 0x50; r[1] = n > 1 ? q[1] : 0; return 2;
    case 0x3E: r[0] = 0x7E; return 1;
    case 0x17: case 0x18:  // una averia ficticia
      r[0] = q[0] + 0x40; r[1] = 1; r[2] = 0x01; r[3] = 0x23; r[4] = 0xA0; return 5;
    case 0x21: {
      uint8_t lid = n > 1 ? q[1] : 0;
      if (lid != 0x80 && lid != 0xA0 && lid != 0xA1 && lid != 0xA2) break;
      r[0] = 0x61; r[1] = lid;
      for (int i = 2; i < 26; i++) r[i] = lid * 7 + i * 13;
      uint16_t rpm = 800 + (millis() / 100) % 40 * 5;  // varia para ver bytes cambiando
      if (lid == 0xA1) { r[2] = rpm & 0xFF; r[3] = rpm >> 8; }  // 16 bits little endian, como la DDCR
      if (lid == 0x80) memcpy(r + 2, "SIM8200212348", 13);
      return 26;
    }
  }
  r[0] = 0x7F; r[1] = q[0]; r[2] = q[0] == 0x21 ? 0x12 : 0x11;
  return 3;
}

bool transact(const uint8_t *d, int n, bool quiet = false) {
  uint8_t f[72];
  int fl = buildFrame(ecu, 0xF1, d, n, f);
  if (!quiet) emit("TX", hex(f, fl));
  lastTx = millis();
  if (sim) {
    uint8_t a[64];
    rspLen = buildFrame(0xF1, ecu, a, simAnswer(d, n, a), rsp);
    rspOff = 3;
    if (!quiet) emit("RX", hex(rsp, rspLen));
    return true;
  }
  while (K.available()) K.read();
  K.write(f, fl);
  K.flush();
  uint8_t eb[72];
  int e = 0;
  uint32_t t = millis();
  while (e < fl && millis() - t < 100) {
    if (K.available()) eb[e++] = K.read();
    yield();
  }
  if (!quiet) emit("ECHO", hex(eb, e));
  if (e < fl || memcmp(eb, f, fl)) emit("DBG", "eco distinto: colision o transceptor mal");
  uint32_t deadline = millis() + 1000;
  while ((int32_t)(deadline - millis()) > 0) {
    int rl = readFrame(rsp, sizeof rsp, deadline - millis());
    if (rl <= 0) {
      emit("ERR", rl ? "INCOMPLETE " + hex(rsp, -rl) : String("TIMEOUT"));
      return false;
    }
    if (!csOk(rsp, rl)) {
      emit("ERR", "CHECKSUM " + hex(rsp, rl));
      return false;
    }
    rspLen = rl;
    rspOff = dataOff(rsp);
    if (!quiet) emit("RX", hex(rsp, rl));
    if (rsp[rspOff] == 0x7F && rl - rspOff - 1 >= 3 && rsp[rspOff + 2] == 0x78) {
      deadline = millis() + 5000;  // respuesta pendiente: seguir esperando
      continue;
    }
    return true;
  }
  emit("ERR", "TIMEOUT");
  return false;
}

bool fastInit() {
  uint8_t sc = 0x81;
  if (!sim) {
    K.end();
    pinMode(K_TX, OUTPUT);
    digitalWrite(K_TX, HIGH);
    delay(300);  // W5: linea en reposo
    digitalWrite(K_TX, LOW);
    delay(25);
    digitalWrite(K_TX, HIGH);
    delay(25);
    kBegin();
  }
  return transact(&sc, 1) && rsp[rspOff] == 0xC1;
}

void handle(String l) {
  l.trim();
  l.toUpperCase();
  if (!l.length()) return;
  if (l == "PING") emit("OK", "PONG");
  else if (l.startsWith("INIT FAST")) {
    String a = l.substring(9);
    a.trim();
    if (a.length()) ecu = strtoul(a.c_str(), 0, 16);
    fastInit() ? emit("OK", "INIT") : emit("ERR", "INIT");
  } else if (l.startsWith("SEND ")) {
    uint8_t d[63];
    int n = parseHex(l.substring(5), d, sizeof d);
    if (n <= 0) emit("ERR", "HEX");
    else if (!allowed(d, n)) emit("ERR", "BLOCKED");
    else if (transact(d, n)) emit("OK", "SEND");
  } else if (l.startsWith("KEEPALIVE ")) {
    ka = l.indexOf(" ON") > 0;
    long ms = l.substring(l.lastIndexOf(' ') + 1).toInt();
    if (ms >= 500 && ms <= 2000) kaMs = ms;
    emit("OK", ka ? "KEEPALIVE ON " + String(kaMs) : String("KEEPALIVE OFF"));
  } else if (l == "SNIFF ON" || l == "SNIFF OFF") {
    sniff = l.endsWith("ON");
    emit("OK", l);
  } else if (l == "SIM ON" || l == "SIM OFF") {
    sim = l.endsWith("ON");
    emit("OK", l);
  } else if (l == "STATUS") {
    emit("OK", String("board=" BOARD " ecu=") + String(ecu, HEX) + " sim=" + String(sim) + " sniff=" + String(sniff) +
                   " keepalive=" + String(ka));
  } else emit("ERR", "CMD " + l);
}

void readLines() {
#if CMD_SERIAL
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { handle(sbuf); sbuf = ""; }
    else if (c != '\r') sbuf += c;
  }
#endif
#if HAS_WIFI
  if (server.hasClient()) {
    if (client) client.stop();
    client = server.available();
    emit("DBG", "cliente TCP conectado");
  }
  while (client && client.available()) {
    char c = client.read();
    if (c == '\n') { handle(tbuf); tbuf = ""; }
    else if (c != '\r') tbuf += c;
  }
#endif
}

void setup() {
#if CMD_SERIAL
  Serial.begin(115200);
#endif
  kBegin();
#ifdef KTX_GATE_PIN
  pinMode(KTX_GATE_PIN, OUTPUT);
  digitalWrite(KTX_GATE_PIN, LOW);  // habilita el TX hacia el transceptor ya pasada la basura del arranque
#endif
#if HAS_WIFI && !defined(ROLE_ECUSIM)
#ifdef STA_SSID
  // AP propio + cliente del hotspot del móvil: el portátil tiene internet (Claude) y ve el puente a la vez
  WiFi.mode(WIFI_AP_STA);
  WiFi.begin(STA_SSID, STA_PASS);
#else
  WiFi.mode(WIFI_AP);
#endif
  WiFi.softAP(WIFI_SSID, WIFI_PASS);
  udp.begin(4210);
  server.begin();
  server.setNoDelay(true);
#endif
#ifdef ROLE_ECUSIM
  emit("DBG", "UCE simulada 0x7A en linea K (" BOARD ")");
#else
  emit("DBG", "puente clio-kline " BOARD " listo");
#endif
}

#ifdef ROLE_ECUSIM
void loop() {
  uint8_t q[80], a[64], f[72];
  int n = readFrame(q, sizeof q, 50);
  if (n <= 0) return;
  if (!csOk(q, n)) { emit("DBG", "trama mala " + hex(q, n)); return; }
  int o = dataOff(q);
  int fl = buildFrame(0xF1, 0x7A, a, simAnswer(q + o, n - o - 1, a), f);
  delay(30);  // P2
  K.write(f, fl);
  K.flush();
  for (uint32_t t = millis(); millis() - t < 50;) if (K.available()) K.read();  // descarta el eco propio
  emit("DBG", hex(q, n) + " -> " + hex(f, fl));
}
#else
void netTasks() {
#if HAS_WIFI
  if (!mdnsOn && WiFi.status() == WL_CONNECTED) {
    mdnsOn = MDNS.begin("clio-kline");  // clio-kline.local
    if (mdnsOn) MDNS.addService("telnet", "tcp", 23);
    emit("DBG", "wifi del movil OK, IP " + WiFi.localIP().toString() + " (clio-kline.local)");
  }
#if defined(ESP8266)
  if (mdnsOn) MDNS.update();
#endif
  if (udp.parsePacket()) {
    char b[8] = {0};
    udp.read(b, 7);
    if (!strncmp(b, "CLIO?", 5)) {
      IPAddress ip = WiFi.status() == WL_CONNECTED ? WiFi.localIP() : WiFi.softAPIP();
      udp.beginPacket(udp.remoteIP(), udp.remotePort());
      udp.print(String("CLIO ") + ip.toString() + " " BOARD);
      udp.endPacket();
    }
  }
#endif
}

void loop() {
  readLines();
  netTasks();
  if (ka && !sniff && millis() - lastTx > kaMs) {
    uint8_t k = 0x3E;
    if (!transact(&k, 1, true)) emit("DBG", "keep-alive sin respuesta");
  }
  if (sniff && !sim && K.available()) {
    uint8_t b[32];
    int n = 0;
    uint32_t t = micros();
    while (n < 32) {
      if (K.available()) { b[n++] = K.read(); t = micros(); }
      else if (micros() - t > 5000) break;  // hueco > 5 ms = fin de trama
    }
    emit("RAW", hex(b, n));
  }
}
#endif
