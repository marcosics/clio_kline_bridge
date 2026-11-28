// Arduino Uno (solo pruebas): K por AltSoftSerial (RX 8, TX 9), comandos por USB a 115200. Sin wifi.
#if defined(ARDUINO) && defined(ARDUINO_ARCH_AVR)
#include <AltSoftSerial.h>
#include <Arduino.h>
#include <EEPROM.h>
#include "../core/cmd.h"
#include "../core/util.h"

static AltSoftSerial ks;   // RX 8, TX 9 (fijos en el Uno)
static const int K_RX = 8, K_TX = 9;
Hal* gPlatform = nullptr;

class UnoHal : public Hal {
 public:
  bool uartOn = false;
  uint32_t ms() override { return millis(); }
  uint32_t us() override { return micros(); }
  void delayMs(uint32_t d) override { delay(d); }
  void idle() override {}
  void kUart(uint32_t baud) override {
    if (uartOn) ks.end();
    ks.begin(baud);
    uartOn = true;
  }
  void kGpio() override {
    if (uartOn) ks.end();
    uartOn = false;
    pinMode(K_TX, OUTPUT);
    digitalWrite(K_TX, HIGH);
    pinMode(K_RX, INPUT);
  }
  void kTx(bool h) override { digitalWrite(K_TX, h ? HIGH : LOW); }
  int kRxLevel() override { return uartOn ? -1 : digitalRead(K_RX); }
  void kWrite(const uint8_t* b, size_t n) override {
    if (uartOn) ks.write(b, n);
  }
  int kRead() override { return uartOn && ks.available() ? ks.read() : -1; }
  void kTxGate(bool) override {}
  void out(const char* line) override { Serial.println(line); }
  const char* board() override { return "uno"; }
  bool loadBlob(void* p, size_t n) override {
    for (size_t i = 0; i < n; i++) ((uint8_t*)p)[i] = EEPROM.read(i);
    return true;
  }
  bool saveBlob(const void* p, size_t n) override {
    for (size_t i = 0; i < n; i++) EEPROM.update(i, ((const uint8_t*)p)[i]);
    return true;
  }
  long freeHeap() override {
    extern int __heap_start, *__brkval;
    int v;
    return (long)((int)&v - (__brkval == 0 ? (int)&__heap_start : (int)__brkval));
  }
};

static UnoHal hal;
static Settings cfg;
static Kwp kwp(hal, cfg);
static Commands cmds(hal, kwp, cfg);
static char buf[LINE_MAX];
static uint8_t len = 0;

void setup() {
  Serial.begin(115200);
  gPlatform = &hal;
  outInit(&hal);
  settingsLoad(cfg);
  gLogLevel = cfg.logLevel;
  kwp.begin();
  cmds.banner();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') { buf[len] = 0; cmds.handle(buf); len = 0; }
    else if (c != '\r' && len < LINE_MAX - 1) buf[len++] = c;
  }
  kwp.poll();
}
#endif
