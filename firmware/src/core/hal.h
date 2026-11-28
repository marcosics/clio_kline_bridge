// Capa de hardware: cada plataforma (ESP8266, ESP32, Uno, PC) la implementa. El núcleo solo habla con esto.
#pragma once
#include "config.h"

class Hal {
 public:
  virtual ~Hal() {}
  virtual uint32_t ms() = 0;
  virtual uint32_t us() = 0;
  virtual void delayMs(uint32_t ms) = 0;   // espera precisa (init); puede ceder a la pila wifi
  virtual void idle() = 0;                 // dentro de esperas largas: ceder CPU, nunca procesar comandos

  // Línea K
  virtual void kUart(uint32_t baud) = 0;   // UART conectada a la K
  virtual void kGpio() = 0;                // UART fuera: TX y RX como GPIO (init y pruebas)
  virtual void kTx(bool high) = 0;         // nivel del TX en modo GPIO
  virtual int kRxLevel() = 0;              // nivel del RX en modo GPIO; -1 si no se puede
  virtual void kWrite(const uint8_t* b, size_t n) = 0;
  virtual int kRead() = 0;                 // un byte o -1
  virtual void kTxGate(bool enable) = 0;   // puerta del TX (ESP-01: GPIO2 activo en bajo); vacío si no hay

  // Salida de texto a todos los clientes (USB, telnet, monitor)
  virtual void out(const char* line) = 0;
  virtual const char* board() = 0;

  // Ajustes persistentes (EEPROM / archivo)
  virtual bool loadBlob(void* p, size_t n) = 0;
  virtual bool saveBlob(const void* p, size_t n) = 0;

  // Opcionales
  virtual void reboot() {}
  virtual long freeHeap() { return -1; }
  virtual void netInfo(char* buf, size_t n) { if (n) buf[0] = 0; }
  virtual bool platformCmd(const char* verb, char* args) { (void)verb; (void)args; return false; }
};
