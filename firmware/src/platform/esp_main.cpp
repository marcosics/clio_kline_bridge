// Plataforma ESP8266 (ESP-01, D1 mini) y ESP32.
// Red: red propia CLIO-KLINE (192.168.4.1) + cliente del hotspot del móvil a la vez.
// Puertos: 23 control (un cliente: la web clio_web.py o telnet), 24 monitor (solo lectura, hasta 3),
//          80 página de diagnóstico con consola, 4210/UDP descubrimiento ("CLIO?"), OTA (espota).
#if defined(ARDUINO) && (defined(ESP8266) || defined(ESP32))
#include <Arduino.h>
#include <ArduinoOTA.h>
#include <EEPROM.h>
#include <WiFiUdp.h>
#if defined(ESP8266)
  #include <ESP8266WebServer.h>
  #include <ESP8266WiFi.h>
  #include <ESP8266mDNS.h>
  typedef ESP8266WebServer WebSrv;
#else
  #include <ESPmDNS.h>
  #include <WebServer.h>
  #include <WiFi.h>
  typedef WebServer WebSrv;
#endif
#include "../core/cmd.h"
#include "../core/ecusim_role.h"
#include "../core/util.h"

#if defined(BOARD_ESP32)
  #define KSER Serial2
  static const int K_RX = 16, K_TX = 17;
  #define CMD_SERIAL 1
  #define LED_PIN 2
  #define BOARD_NAME "esp32"
#elif defined(BOARD_D1MINI)
  #define KSER Serial
  static const int K_RX = 13, K_TX = 15;   // UART0 intercambiado
  #define LOG_SERIAL1 1                     // log por GPIO2 (D4) a 115200
  #define BOARD_NAME "d1mini"
#else
  #define KSER Serial
  static const int K_RX = 3, K_TX = 1;      // ESP-01: el único UART es la línea K
  #define BOARD_NAME "esp01"
#endif
#ifndef CMD_SERIAL
  #define CMD_SERIAL 0
#endif

Hal* gPlatform = nullptr;
static Settings cfg;

// ---------------------------------------------------------------- HAL
class EspHal : public Hal {
 public:
  bool uartOn = false;
  String* capture = nullptr;   // salida de un comando lanzado desde la página web
  WiFiClient* ctrl = nullptr;
  WiFiClient* mon = nullptr;
  int nmon = 0;

  uint32_t ms() override { return millis(); }
  uint32_t us() override { return micros(); }
  void delayMs(uint32_t d) override { delay(d); }
  void idle() override { yield(); }

  void kUart(uint32_t baud) override {
    if (uartOn) KSER.end();
#if defined(ESP32)
    KSER.setRxBufferSize(1024);
    KSER.begin(baud, SERIAL_8N1, K_RX, K_TX);
#else
    KSER.setRxBufferSize(1024);
    KSER.begin(baud, SERIAL_8N1);
  #if defined(BOARD_D1MINI)
    KSER.swap();
  #endif
    KSER.setDebugOutput(false);
#endif
    uartOn = true;
  }
  void kGpio() override {
    if (uartOn) {
      KSER.flush();
      KSER.end();
    }
    uartOn = false;
    pinMode(K_TX, OUTPUT);
    digitalWrite(K_TX, HIGH);
    pinMode(K_RX, INPUT);
  }
  void kTx(bool high) override { digitalWrite(K_TX, high ? HIGH : LOW); }
  int kRxLevel() override { return uartOn ? -1 : digitalRead(K_RX); }
  void kWrite(const uint8_t* b, size_t n) override {
    if (uartOn) KSER.write(b, n);
  }
  int kRead() override { return uartOn && KSER.available() ? KSER.read() : -1; }
  void kTxGate(bool enable) override {
#ifdef KTX_GATE_PIN
    digitalWrite(KTX_GATE_PIN, enable ? LOW : HIGH);
#else
    (void)enable;
#endif
  }

  void out(const char* line) override {
    for (int i = 0; i < nmon; i++)
      if (mon[i] && mon[i].connected()) { mon[i].print(line); mon[i].print("\r\n"); }
    if (capture) {   // comando de la página web: solo a la página (y monitores), no a la web del PC
      if (capture->length() < 12000) { *capture += line; *capture += '\n'; }
      return;
    }
#if CMD_SERIAL
    Serial.println(line);
#endif
#ifdef LOG_SERIAL1
    Serial1.println(line);
#endif
    if (ctrl && *ctrl && ctrl->connected()) {
      ctrl->print(line);
      ctrl->print("\r\n");
    }
  }
  const char* board() override { return BOARD_NAME; }
  bool loadBlob(void* p, size_t n) override {
    for (size_t i = 0; i < n; i++) ((uint8_t*)p)[i] = EEPROM.read(i);
    return true;
  }
  bool saveBlob(const void* p, size_t n) override {
    for (size_t i = 0; i < n; i++) EEPROM.write(i, ((const uint8_t*)p)[i]);
    return EEPROM.commit();
  }
  void reboot() override { ESP.restart(); }
  long freeHeap() override { return (long)ESP.getFreeHeap(); }
  void netInfo(char* b, size_t n) override;
  bool platformCmd(const char* verb, char* args) override;
};

static EspHal hal;
static Kwp kwp(hal, cfg);
static Commands cmds(hal, kwp, cfg);

// ---------------------------------------------------------------- red
static WiFiServer ctrlSrv(23), monSrv(24);
static WiFiClient ctrl, mon[3];
static WiFiUDP udp;
static WebSrv web(80);
static char ctrlBuf[LINE_MAX];
static size_t ctrlLen = 0;
static bool staWasUp = false, apOn = false, otaBusy = false;
static uint32_t staChangeMs = 0;
#if CMD_SERIAL
static char serBuf[LINE_MAX];
static size_t serLen = 0;
#endif

static bool staUp() { return WiFi.status() == WL_CONNECTED; }

void EspHal::netInfo(char* b, size_t n) {
  int monc = 0;
  for (auto& m : ::mon) monc += (m && m.connected()) ? 1 : 0;
  if (!cfg.staSsid[0])
    snprintf(b, n, "sta=off ap=%s(%s,%d) tcp=%d mon=%d", cfg.apSsid, WiFi.softAPIP().toString().c_str(),
             (int)WiFi.softAPgetStationNum(), (int)(::ctrl && ::ctrl.connected()), monc);
  else
    snprintf(b, n, "sta=%s(%s%s,%ddBm) ap=%s tcp=%d mon=%d", cfg.staSsid, staUp() ? "" : "sin conexion ",
             staUp() ? WiFi.localIP().toString().c_str() : "", staUp() ? (int)WiFi.RSSI() : 0,
             apOn ? WiFi.softAPIP().toString().c_str() : "off", (int)(::ctrl && ::ctrl.connected()), monc);
}

static void wifiApply() {
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  bool sta = cfg.staSsid[0] != 0;
#if defined(ESP8266)
  WiFi.hostname(cfg.host);
  WiFi.setSleepMode(WIFI_NONE_SLEEP);   // menos latencia en telnet
#else
  WiFi.setHostname(cfg.host);
  WiFi.setSleep(false);
#endif
  WiFi.mode(sta ? WIFI_AP_STA : WIFI_AP);
  WiFi.softAP(cfg.apSsid, strlen(cfg.apPass) >= 8 ? cfg.apPass : nullptr);
  apOn = true;
  if (sta) WiFi.begin(cfg.staSsid, cfg.staPass);
  emit("DBG", "wifi: red propia %s (%s)%s%s", cfg.apSsid, WiFi.softAPIP().toString().c_str(),
       sta ? " + movil " : "", sta ? cfg.staSsid : "");
}

static void wifiLoop() {
  bool up = staUp();
  if (up != staWasUp) {
    staWasUp = up;
    staChangeMs = millis();
    if (up) {
      emit("EVT", "wifi del movil conectado: IP %s (%s.local) %ddBm", WiFi.localIP().toString().c_str(), cfg.host,
           (int)WiFi.RSSI());
#if defined(ESP8266)
      MDNS.notifyAPChange();
#endif
    } else if (cfg.staSsid[0]) {
      emit("EVT", "wifi del movil perdido (sigue la red propia %s)", apOn ? cfg.apSsid : "apagada");
    }
  }
  if (!cfg.apAlways && cfg.staSsid[0]) {   // AP_ALWAYS=0: apagar la red propia si hay móvil estable
    if (up && apOn && millis() - staChangeMs > 30000) {
      WiFi.mode(WIFI_STA);
      apOn = false;
      emit("EVT", "red propia apagada (AP_ALWAYS=0, hay wifi del movil)");
    }
    if (!up && !apOn && millis() - staChangeMs > 60000) {
      WiFi.mode(WIFI_AP_STA);
      WiFi.softAP(cfg.apSsid, strlen(cfg.apPass) >= 8 ? cfg.apPass : nullptr);
      apOn = true;
      emit("EVT", "red propia encendida otra vez (sin wifi del movil)");
    }
  }
}

static void udpLoop() {
  if (!udp.parsePacket()) return;
  char b[8] = {0};
  udp.read(b, 7);
  if (strncmp(b, "CLIO?", 5)) return;
  IPAddress ip = (staUp() && udp.remoteIP() != WiFi.softAPIP()) ? WiFi.localIP() : WiFi.softAPIP();
  udp.beginPacket(udp.remoteIP(), udp.remotePort());
  udp.print(String("CLIO ") + ip.toString() + " " BOARD_NAME " " FW_VERSION);
  udp.endPacket();
}

static void tcpLoop() {
  if (ctrlSrv.hasClient()) {
    WiFiClient c = ctrlSrv.accept();
    if (ctrl && ctrl.connected()) {
      ctrl.print("EVT 0 otro cliente se ha conectado al puerto 23: este se cierra\r\n");
      ctrl.stop();
    }
    ctrl = c;
    ctrl.setNoDelay(true);
    ctrlLen = 0;
    cmds.banner();
  }
  while (ctrl && ctrl.connected() && ctrl.available()) {
    char ch = (char)ctrl.read();
    if (ch == '\n') {
      ctrlBuf[ctrlLen] = 0;
      cmds.handle(ctrlBuf);
      ctrlLen = 0;
      break;   // un comando por vuelta: deja respirar al wifi y al keep-alive
    } else if (ch != '\r' && ctrlLen < LINE_MAX - 1) {
      ctrlBuf[ctrlLen++] = ch;
    }
  }
  if (monSrv.hasClient()) {
    WiFiClient c = monSrv.accept();
    int slot = -1;
    for (int i = 0; i < 3; i++)
      if (!mon[i] || !mon[i].connected()) { slot = i; break; }
    if (slot < 0) { c.print("monitor lleno (3)\r\n"); c.stop(); }
    else {
      mon[slot] = c;
      mon[slot].setNoDelay(true);
      mon[slot].print("INFO 0 monitor clio-kline: solo lectura, ves todo lo que pasa\r\n");
    }
  }
#if CMD_SERIAL
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n') { serBuf[serLen] = 0; cmds.handle(serBuf); serLen = 0; }
    else if (ch != '\r' && serLen < LINE_MAX - 1) serBuf[serLen++] = ch;
  }
#endif
}

// ---------------------------------------------------------------- página de diagnóstico
static const char PAGE[] PROGMEM = R"HTML(<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>clio-kline</title><style>
body{font:14px system-ui,sans-serif;margin:0;background:#f4f5f7;color:#1b1f24}@media(prefers-color-scheme:dark){body{background:#15171a;color:#e6e8eb}section{background:#1f2226!important}input,pre{background:#111!important;color:#e6e8eb!important}}
header{padding:10px 14px;background:#0a66c2;color:#fff}section{background:#fff;margin:10px;padding:10px 12px;border-radius:8px}
h2{font-size:12px;text-transform:uppercase;color:#888;margin:0 0 6px}pre{background:#f0f1f3;padding:8px;max-height:320px;overflow:auto;font:12px monospace;white-space:pre-wrap}
input,button{font:inherit;padding:6px 8px;border-radius:6px;border:1px solid #ccc}button{background:#0a66c2;color:#fff;border:0}.row{display:flex;gap:6px;flex-wrap:wrap}
table td{padding:2px 8px 2px 0;font:12px monospace}</style></head><body>
<header><b>clio-kline</b> · puente línea K · <span id="v"></span></header>
<section><h2>Estado</h2><table id="st"></table></section>
<section><h2>Consola</h2><div class="row"><input id="c" placeholder="TEST LINE · TEST ECHO · INIT FAST 7A · SEND 2180 · STATS · HELP" style="flex:1"><button onclick="run()">Enviar</button></div>
<div class="row" style="margin-top:6px"><button onclick="run('TEST LINE')">Test línea</button><button onclick="run('TEST ECHO 8')">Test eco</button><button onclick="run('INIT FAST 7A')">Init 7A</button><button onclick="run('SEND 2180')">Ident</button><button onclick="run('STATS')">Stats</button></div><pre id="o"></pre>
<p style="font-size:12px;color:#888">Solo lectura. Si la web del PC está conectada al puerto 23, no uses la línea a la vez desde aquí.</p></section>
<section><h2>Wifi del móvil</h2><div class="row"><input id="s" placeholder="nombre de la zona wifi"><input id="p" placeholder="clave" type="password"><button onclick="wifi()">Guardar y conectar</button><button onclick="scan()">Buscar redes</button></div><pre id="w"></pre></section>
<section><h2>Log</h2><pre id="l"></pre></section>
<script>
const $=i=>document.getElementById(i);
async function st(){try{const j=await (await fetch('/status')).json();$('v').textContent=j.board+' fw '+j.fw;
$('st').innerHTML=Object.entries(j).map(([k,v])=>`<tr><td>${k}</td><td>${typeof v==='object'?JSON.stringify(v):v}</td></tr>`).join('');
$('l').textContent=await (await fetch('/log')).text()}catch(e){}}
async function run(c){c=c||$('c').value;$('o').textContent='> '+c+'\n'+await (await fetch('/cmd?c='+encodeURIComponent(c))).text()+'\n'+$('o').textContent}
async function wifi(){const b=new URLSearchParams({ssid:$('s').value,pass:$('p').value});$('w').textContent=await (await fetch('/wifi',{method:'POST',body:b})).text()}
async function scan(){$('w').textContent='buscando…';$('w').textContent=await (await fetch('/cmd?c=SCAN')).text()}
$('c').onkeydown=e=>{if(e.key==='Enter')run()};st();setInterval(st,3000);
</script></body></html>)HTML";

static void logLine(const char* l, void* s) {
  *(String*)s += l;
  *(String*)s += '\n';
}

static void webSetup() {
  web.on("/", []() { web.send_P(200, "text/html; charset=utf-8", PAGE); });
  web.on("/status", []() {
    char net[200];
    hal.netInfo(net, sizeof net);
    KStats& s = kwp.st;
    String j = "{";
    j += "\"board\":\"" BOARD_NAME "\",\"fw\":\"" FW_VERSION "\",\"uptime_s\":" + String(millis() / 1000);
    j += ",\"heap\":" + String(ESP.getFreeHeap()) + ",\"link\":\"" + kwp.linkName() + "\"";
    char e[8];
    snprintf(e, sizeof e, "%02X", kwp.ecu);
    j += ",\"ecu\":\"" + String(e) + "\",\"sim\":" + String(kwp.sim) + ",\"sniff\":" + String(kwp.sniff);
    j += ",\"keepalive\":" + String(kwp.ka) + ",\"baud\":" + String(cfg.baud);
    j += ",\"stats\":{\"tx\":" + String(s.tx) + ",\"rx\":" + String(s.rx) + ",\"timeouts\":" + String(s.timeouts) +
         ",\"checksum\":" + String(s.checksum) + ",\"echo_err\":" + String(s.echoErr) + ",\"no_echo\":" +
         String(s.noEcho) + ",\"inits\":" + String(s.inits) + ",\"init_fail\":" + String(s.initFail) + "}";
    String n = net;
    n.replace("\"", "'");
    j += ",\"red\":\"" + n + "\"}";
    web.send(200, "application/json", j);
  });
  web.on("/log", []() {
    String s;
    logRing(logLine, &s);
    web.send(200, "text/plain; charset=utf-8", s);
  });
  web.on("/cmd", []() {
    String c = web.arg("c"), outp;
    char line[LINE_MAX];
    strncpy(line, c.c_str(), sizeof line - 1);
    line[sizeof line - 1] = 0;
    hal.capture = &outp;
    cmds.handle(line);
    hal.capture = nullptr;
    web.send(200, "text/plain; charset=utf-8", outp);
  });
  web.on("/wifi", HTTP_POST, []() {
    char err[80];
    if (!settingsSet(cfg, "STA_SSID", web.arg("ssid").c_str(), err, sizeof err) ||
        !settingsSet(cfg, "STA_PASS", web.arg("pass").c_str(), err, sizeof err)) {
      web.send(400, "text/plain", err);
      return;
    }
    settingsSave(cfg);
    web.send(200, "text/plain; charset=utf-8",
             String("Guardado. Conectando a ") + cfg.staSsid + "... (en la red del movil: " + cfg.host + ".local)");
    delay(200);
    wifiApply();
  });
  web.onNotFound([]() { web.send(404, "text/plain", "no existe"); });
  web.begin();
}

// ---------------------------------------------------------------- comandos propios del ESP
static void wifiCmd(char* args) {
  // WIFI <ssid> <clave>  ·  WIFI "nombre con espacios" clave  ·  WIFI OFF
  char* a = trim(args);
  char ssid[33] = {0}, pass[65] = {0};
  if (!strcasecmp(a, "OFF")) {
    cfg.staSsid[0] = cfg.staPass[0] = 0;
  } else {
    if (*a == '"') {
      char* e = strchr(a + 1, '"');
      if (!e) { emit("ERR", "WIFI \"nombre\" clave"); return; }
      *e = 0;
      strncpy(ssid, a + 1, 32);
      a = trim(e + 1);
    } else {
      char* t = nextTok(&a);
      if (!t) { emit("ERR", "WIFI <ssid> <clave> | WIFI OFF"); return; }
      strncpy(ssid, t, 32);
    }
    strncpy(pass, trim(a), 64);
    char err[80];
    if (!settingsSet(cfg, "STA_SSID", ssid, err, sizeof err) || !settingsSet(cfg, "STA_PASS", pass, err, sizeof err)) {
      emit("ERR", "%s", err);
      return;
    }
  }
  if (!settingsSave(cfg)) { emit("ERR", "WIFI no se pudo guardar"); return; }
  emit("OK", "WIFI %s guardado; reconectando (mira NET en unos segundos)", cfg.staSsid[0] ? cfg.staSsid : "OFF");
  delay(100);
  wifiApply();
}

bool EspHal::platformCmd(const char* verb, char* args) {
  if (!strcmp(verb, "WIFI")) { wifiCmd(args); return true; }
  if (!strcmp(verb, "NET")) {
    char b[200];
    netInfo(b, sizeof b);
    emit("OK", "%s mac=%s host=%s.local", b, WiFi.macAddress().c_str(), cfg.host);
    return true;
  }
  if (!strcmp(verb, "SCAN")) {
    int n = WiFi.scanNetworks();
    for (int i = 0; i < n && i < 20; i++)
      emit("INFO", "%-32s %4ddBm canal %d%s", WiFi.SSID(i).c_str(), (int)WiFi.RSSI(i), (int)WiFi.channel(i),
#if defined(ESP8266)
           WiFi.encryptionType(i) == ENC_TYPE_NONE ? " abierta" : "");
#else
           WiFi.encryptionType(i) == WIFI_AUTH_OPEN ? " abierta" : "");
#endif
    WiFi.scanDelete();
    emit("OK", "SCAN %d redes", n);
    return true;
  }
  return false;
}

static void otaSetup() {
  ArduinoOTA.setHostname(cfg.host);
  if (strlen(cfg.apPass) >= 8) ArduinoOTA.setPassword(cfg.apPass);
  ArduinoOTA.onStart([]() {
    otaBusy = true;
    kwp.ka = false;
    kwp.sniff = false;
    emit("EVT", "OTA: actualizando el firmware, no quites la corriente");
  });
  ArduinoOTA.onEnd([]() { emit("EVT", "OTA terminada: reinicio"); });
  ArduinoOTA.onError([](ota_error_t e) {
    otaBusy = false;
    emit("EVT", "OTA error %d", (int)e);
  });
  ArduinoOTA.begin();   // arranca también el mDNS (clio-kline.local)
  MDNS.addService("telnet", "tcp", 23);
  MDNS.addService("http", "tcp", 80);
}

static const char* resetReason() {
#if defined(ESP8266)
  static String r;
  r = ESP.getResetReason();
  return r.c_str();
#else
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return "encendido";
    case ESP_RST_SW: return "reinicio por software";
    case ESP_RST_PANIC: return "fallo (panic)";
    case ESP_RST_INT_WDT: case ESP_RST_TASK_WDT: case ESP_RST_WDT: return "watchdog";
    case ESP_RST_BROWNOUT: return "caida de tension (brownout)";
    default: return "otro";
  }
#endif
}

#ifdef ROLE_ECUSIM
static EcuSimRole role(hal);
#endif

void setup() {
#ifdef KTX_GATE_PIN
  pinMode(KTX_GATE_PIN, OUTPUT);
  digitalWrite(KTX_GATE_PIN, HIGH);   // TX bloqueado mientras el ESP saca basura al arrancar
#endif
#if CMD_SERIAL
  Serial.begin(115200);
#endif
#ifdef LOG_SERIAL1
  Serial1.begin(115200);
#endif
#ifdef LED_PIN
  pinMode(LED_PIN, OUTPUT);
#endif
  gPlatform = &hal;
  outInit(&hal);
  EEPROM.begin(512);
  bool loaded = settingsLoad(cfg);
  gLogLevel = cfg.logLevel;
  hal.ctrl = &ctrl;
  hal.mon = mon;
  hal.nmon = 3;
#ifdef ROLE_ECUSIM
  role.begin();
  return;
#endif
  kwp.begin();
  delay(50);
  while (KSER.available()) KSER.read();
  hal.kTxGate(true);                  // ya se puede transmitir a la K
  emit("DBG", "arranque (%s), ajustes %s, fw %s %s", resetReason(), loaded ? "de la EEPROM" : "por defecto",
       FW_VERSION, BOARD_NAME);
  wifiApply();
  ctrlSrv.begin();
  ctrlSrv.setNoDelay(true);
  monSrv.begin();
  udp.begin(4210);
  webSetup();
  otaSetup();
}

void loop() {
#ifdef ROLE_ECUSIM
  role.loop();
  return;
#endif
  ArduinoOTA.handle();
  if (otaBusy) return;
#if defined(ESP8266)
  MDNS.update();
#endif
  wifiLoop();
  udpLoop();
  tcpLoop();
  web.handleClient();
  kwp.poll();
#ifdef LED_PIN
  digitalWrite(LED_PIN, kwp.link == Link::Up ? HIGH : (millis() / 500) % 2);
#endif
}
#endif
