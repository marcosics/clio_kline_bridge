// Comandos de texto del puente (iguales por USB, telnet :23 y la página web del ESP).
// Cada comando termina con UNA línea OK o ERR; lo asíncrono va con EVT/DBG/RAW para no confundir a la web.
#pragma once
#include "kwp.h"

class Commands {
 public:
  Commands(Hal& h, Kwp& k, Settings& s) : hal(h), kwp(k), cfg(s) {}
  void handle(char* line);   // la línea se modifica
  void banner();

 private:
  Hal& hal;
  Kwp& kwp;
  Settings& cfg;
  void help();
  void status();
  void stats(bool reset);
};
