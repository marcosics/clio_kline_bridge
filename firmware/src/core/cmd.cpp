#include "cmd.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "util.h"

extern char gDetail[];

void Commands::banner() {
  emit("INFO", "clio-kline fw %s placa %s. HELP para ver los comandos. Solo lectura: 10C0 3E 21 17 18 1A.", FW_VERSION,
       hal.board());
}

void Commands::help() {
#if defined(ARDUINO_ARCH_AVR)
  emit("INFO", "PING VERSION STATUS STATS INIT SEND ECU KEEPALIVE SNIFF SIM TEST BAUD TIMING LOG CONFIG SET SAVE");
#else
  static const char* const H[] = {
      "PING | VERSION | STATUS | STATS [RESET] | HELP",
      "INIT FAST [ecu] [intentos] | INIT SLOW [ecu]   init rapido (DDCR) o a 5 baudios",
      "SEND <hex>   peticion KWP sin cabecera ni checksum (solo 10C0 3E 21 17 18 1A)",
      "ECU <hex> | KEEPALIVE ON [ms] | KEEPALIVE OFF | SNIFF ON|OFF | SIM ON|OFF",
      "TEST LINE   niveles de la K (sin UCE) | TEST ECHO [n]   eco de n bytes por la K",
      "BAUD <n> | TIMING | LOG 0-3 | LOGDUMP",
      "CONFIG | SET <clave> <valor> | SAVE | FACTORY | REBOOT",
      "WIFI <ssid> <clave> | WIFI OFF | NET | SCAN   (wifi del movil; ESP)",
  };
  for (const char* l : H) emit("INFO", "%s", l);
#endif
  emit("OK", "HELP");
}

void Commands::status() {
  char net[200];
  hal.netInfo(net, sizeof net);
  emit("OK", "board=%s fw=%s link=%s ecu=%02X tester=%02X baud=%lu kb=%02X%02X sim=%d sniff=%d ka=%d/%u up=%lus "
       "heap=%ld echo=%u retries=%u log=%u %s",
       hal.board(), FW_VERSION, kwp.linkName(), kwp.ecu, cfg.tester, (unsigned long)cfg.baud, kwp.kb1, kwp.kb2, kwp.sim,
       kwp.sniff, kwp.ka, cfg.kaMs, (unsigned long)(hal.ms() / 1000), hal.freeHeap(), cfg.expectEcho, cfg.retries,
       gLogLevel, net);
}

void Commands::stats(bool reset) {
  KStats& s = kwp.st;
  emit("OK", "tx=%lu rx=%lu neg=%lu timeouts=%lu checksum=%lu incomplete=%lu echo_err=%lu no_echo=%lu inits=%lu "
       "init_fail=%lu ka_fail=%lu retries=%lu junk=%lu",
       (unsigned long)s.tx, (unsigned long)s.rx, (unsigned long)s.neg, (unsigned long)s.timeouts,
       (unsigned long)s.checksum, (unsigned long)s.incomplete, (unsigned long)s.echoErr, (unsigned long)s.noEcho,
       (unsigned long)s.inits, (unsigned long)s.initFail, (unsigned long)s.kaFail, (unsigned long)s.retries,
       (unsigned long)s.junk);
  if (reset) memset(&s, 0, sizeof s);
}

static bool isOn(const char* a) { return a && (!strcmp(a, "ON") || !strcmp(a, "1")); }
static bool isOff(const char* a) { return a && (!strcmp(a, "OFF") || !strcmp(a, "0")); }

static void ringOut(const char* l, void* n) {
  emit("INFO", "| %s", l);
  (*(int*)n)++;
}

void Commands::handle(char* line) {
  char* rest = trim(line);
  if (!*rest || *rest == '#') return;
  char* verb = nextTok(&rest);
  upcase(verb);
  char* args = trim(rest);   // los argumentos conservan mayúsculas/minúsculas (SSID y claves)
  char up[64];               // primer argumento en mayúsculas para comparar
  {
    size_t i = 0;
    while (args[i] && args[i] != ' ' && i < sizeof up - 1) { up[i] = args[i]; i++; }
    up[i] = 0;
    upcase(up);
  }
  char why[WHY_LEN] = {0};

  if (!strcmp(verb, "PING")) { emit("OK", "PONG"); return; }
  if (!strcmp(verb, "VERSION")) { emit("OK", "FW %s %s", FW_VERSION, hal.board()); return; }
  if (!strcmp(verb, "HELP") || !strcmp(verb, "?")) { help(); return; }
  if (!strcmp(verb, "STATUS")) { status(); return; }
  if (!strcmp(verb, "STATS")) { stats(!strcmp(up, "RESET")); return; }

  if (!strcmp(verb, "INIT")) {
    char* a = args;
    char* mode = nextTok(&a);
    char* e = nextTok(&a);
    char* tries = nextTok(&a);
    if (mode) upcase(mode);
    uint32_t v;
    if (e) {
      if (!parseU32(e, &v, 16) || v > 0xFF) { emit("ERR", "INIT direccion invalida %s", e); return; }
      kwp.ecu = (uint8_t)v;
    }
    bool slow = mode && !strcmp(mode, "SLOW");
    if (mode && !slow && strcmp(mode, "FAST")) { emit("ERR", "INIT FAST|SLOW [ecu]"); return; }
    uint32_t n = 2;
    if (tries) parseU32(tries, &n);
    if (n < 1) n = 1;
    if (n > 5) n = 5;
    kwp.sniff = false;
    bool ok = false;
    for (uint32_t i = 0; i < (slow ? 1 : n) && !ok; i++) {
      if (i) { emit("EVT", "init %02X: reintento %lu tras '%s'", kwp.ecu, (unsigned long)i, why); hal.delayMs(300); }
      ok = slow ? kwp.slowInit(why, sizeof why) : kwp.fastInit(why, sizeof why);
    }
    if (ok) emit("OK", "INIT %02X kb=%02X%02X", kwp.ecu, kwp.kb1, kwp.kb2);
    else emit("ERR", "INIT %02X %s", kwp.ecu, why);
    return;
  }

  if (!strcmp(verb, "SEND")) {
    static uint8_t d[KBUF];
    int n = hexToBytes(args, d, KBUF - 6);
    if (n <= 0) { emit("ERR", "HEX invalido '%s'", args); return; }
    KRes r = kwp.request(d, n);
    if (r == KRes::Ok) emit("OK", "SEND");
    else if (r == KRes::Blocked) emit("ERR", "BLOCKED servicio %02X (solo lectura: 10C0 3E 21 17 18 1A)", d[0]);
    else emit("ERR", "%s %s", kresName(r), gDetail);
    return;
  }

  if (!strcmp(verb, "ECU")) {
    uint32_t v;
    if (!parseU32(args, &v, 16) || v > 0xFF) { emit("ERR", "ECU <hex>"); return; }
    kwp.ecu = (uint8_t)v;
    kwp.link = Link::Idle;
    kwp.ka = false;
    emit("OK", "ECU %02X (haz INIT)", kwp.ecu);
    return;
  }

  if (!strcmp(verb, "KEEPALIVE")) {
    char* a = args;
    nextTok(&a);
    char* msTok = nextTok(&a);
    uint32_t v;
    if (msTok && parseU32(msTok, &v) && v >= 300 && v <= 4000) cfg.kaMs = (uint16_t)v;
    if (isOn(up)) kwp.ka = true;
    else if (isOff(up)) kwp.ka = false;
    else { emit("ERR", "KEEPALIVE ON [ms] | OFF"); return; }
    emit("OK", "KEEPALIVE %s %u", kwp.ka ? "ON" : "OFF", cfg.kaMs);
    return;
  }

  if (!strcmp(verb, "SNIFF") || !strcmp(verb, "SIM")) {
    if (!isOn(up) && !isOff(up)) { emit("ERR", "%s ON|OFF", verb); return; }
    bool on = isOn(up);
    if (verb[1] == 'N') {
      kwp.sniff = on;
      if (on) kwp.ka = false;
    } else {
      kwp.sim = on;
      kwp.link = Link::Idle;
      kwp.ka = false;
    }
    emit("OK", "%s %s", verb, on ? "ON" : "OFF");
    return;
  }

  if (!strcmp(verb, "BAUD")) {
    uint32_t v;
    if (!parseU32(args, &v) || v < 1200 || v > 115200) { emit("ERR", "BAUD 1200-115200"); return; }
    cfg.baud = v;
    hal.kUart(v);
    emit("OK", "BAUD %lu", (unsigned long)v);
    return;
  }

  if (!strcmp(verb, "LOG")) {
    uint32_t v;
    if (!parseU32(args, &v) || v > 3) { emit("ERR", "LOG 0-3 (0 errores, 1 normal, 2 +eco, 3 todo)"); return; }
    gLogLevel = cfg.logLevel = (uint8_t)v;
    emit("OK", "LOG %u", gLogLevel);
    return;
  }

  if (!strcmp(verb, "TIMING")) {
    if (*args) {
      char* a = args;
      char* k = nextTok(&a);
      upcase(k);
      if (!settingsSet(cfg, k, trim(a), why, sizeof why)) { emit("ERR", "%s", why); return; }
    }
    emit("OK", "P1MAX=%u P2MAX=%u P2EXT=%u P3MIN=%u P4=%u W5=%u TINIL=%u TWUP=%u", cfg.t.p1max, cfg.t.p2max,
         cfg.t.p2ext, cfg.t.p3min, cfg.t.p4, cfg.t.w5, cfg.t.tinil, cfg.t.twup);
    return;
  }

  if (!strcmp(verb, "TEST")) {
    bool ok;
    if (!strcmp(up, "LINE")) ok = kwp.testLine(why, sizeof why);
    else if (!strcmp(up, "ECHO")) {
      char* a = args;
      nextTok(&a);
      uint32_t n = 8;
      char* t = nextTok(&a);
      if (t) parseU32(t, &n);
      ok = kwp.testEcho((int)n, why, sizeof why);
    } else { emit("ERR", "TEST LINE | TEST ECHO [n]"); return; }
    if (ok) emit("OK", "TEST %s %s", up, why);
    else emit("ERR", "TEST %s %s", up, why);
    return;
  }

  if (!strcmp(verb, "LOGDUMP")) {
    int n = 0;
    logRing(ringOut, &n);
    emit("OK", "LOGDUMP %d lineas", n);
    return;
  }

  if (!strcmp(verb, "CONFIG")) {
    settingsShow(cfg);
    emit("OK", "CONFIG (SET clave valor, luego SAVE)");
    return;
  }

  if (!strcmp(verb, "SET")) {
    char* a = args;
    char* k = nextTok(&a);
    if (!k) { emit("ERR", "SET <clave> <valor>"); return; }
    upcase(k);
    if (!settingsSet(cfg, k, trim(a), why, sizeof why)) { emit("ERR", "%s", why); return; }
    if (!strcmp(k, "LOG")) gLogLevel = cfg.logLevel;
    if (!strcmp(k, "ECU")) kwp.ecu = cfg.ecu;
    if (!strcmp(k, "BAUD")) hal.kUart(cfg.baud);
    emit("OK", "SET %s (SAVE para guardarlo)", k);
    return;
  }

  if (!strcmp(verb, "SAVE")) {
    if (settingsSave(cfg)) emit("OK", "SAVE");
    else emit("ERR", "SAVE no se pudo guardar");
    return;
  }

  if (!strcmp(verb, "FACTORY")) {
    settingsDefaults(cfg);
    settingsSave(cfg);
    gLogLevel = cfg.logLevel;
    emit("OK", "FACTORY ajustes de fabrica guardados (REBOOT para aplicar el wifi)");
    return;
  }

  if (!strcmp(verb, "REBOOT")) {
    emit("OK", "REBOOT");
    hal.delayMs(200);
    hal.reboot();
    return;
  }

  if (hal.platformCmd(verb, args)) return;
  emit("ERR", "CMD desconocido '%s' (HELP)", verb);
}
