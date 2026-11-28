// Centralitas simuladas: inyección DDCR 0x7A, UCH 0x26 y ABS 0x28, con un ciclo de conducción de 60 s.
// La usan SIM ON (sin línea), el papel ROLE_ECUSIM (en la línea real) y la línea virtual del PC.
#pragma once
#include "config.h"

bool ecuSimPresent(uint8_t ecu);
// Respuesta (solo datos, sin cabecera) a la petición q. Devuelve la longitud; 0 = no contesta.
int ecuSimAnswer(uint8_t ecu, const uint8_t* q, int n, uint8_t* r, uint32_t ms);
