# Firmware clio-kline 2.x (puente línea K)

Un solo núcleo (`src/core/`) para todas las placas:
- **Línea K y KWP2000:**
  - Init rápido y a 5 baudios.
  - Eco half-duplex comprobado byte a byte.
  - Tiempos P1-P4 y W5 configurables.
  - Respuesta pendiente `7F xx 78`.
  - Reintentos.
  - Keep-alive con detección de enlace perdido.
  - Sniffer.
  - Lista blanca de servicios: solo lectura, también en el firmware.
- **Plataformas** (`src/platform/`):
  - ESP8266 (ESP-01, D1 mini) y ESP32: wifi, telnet, monitor, página web, OTA y descubrimiento.
  - Arduino Uno: solo pruebas.
  - PC (`native`): el mismo firmware con una línea K virtual. Las pruebas de la web lo usan.

## 1. Grabar el ESP-01 (la primera vez, con el adaptador USB-ESP01)

1. Saca el ESP-01 de la placa y ponlo en el adaptador. Si el adaptador no tiene botón, haz un puente de GPIO0 a GND al enchufarlo.
2. `python -m platformio run -d firmware -e esp01 -t upload`
3. Quita el puente, vuelve a poner el ESP en la placa y dale corriente.

A partir de aquí ya no hace falta sacarlo, porque se graba por wifi (OTA):
`python -m platformio run -d firmware -e esp01_ota -t upload`
El PC tiene que estar en la misma red que el ESP. La clave de la OTA es la de la red propia (por defecto `clio1234`).

## 2. Primer arranque y depuración (en la mesa, sin coche)

Alimenta la placa: 12 V en la entrada OBD 16 (fuente o batería de 9-12 V) y masa.

1. Desde el portátil o el móvil, conéctate a la wifi **CLIO-KLINE** (clave `clio1234`).
2. Abre **http://192.168.4.1**: estado, consola, log y configuración del wifi del móvil.
3. En la consola de la página:
   - `TEST LINE`: comprueba los niveles de la K sin centralita.
     - `OK … Hardware bien` → TX, K y RX correctos.
     - `reposo=0` → la K está en bajo. Revisa los 12 V en R10, un corto a masa o que el LM339 tenga 3,3 V.
     - `tx0->1` → el TX no baja la K. Revisa GPIO2 (la puerta), D2, R7, los comparadores de TX y R10.
   - `TEST ECHO 8` → manda 8 bytes y los lee de vuelta por la K.
     - `8/8` → la UART, el LM339 y el umbral (R1/R2/R3) están bien.
     - `0/8` → no vuelve nada.
     - Errores sueltos → ruido o umbral.
4. Wifi del móvil: en la página, *Wifi del móvil* → nombre y clave → *Guardar y conectar*. Por telnet también vale: `WIFI MiZona MiClave`. Se guarda en la EEPROM y no hay que recompilar.
5. Telnet (PuTTY/Tera Term) al puerto **23** para mandar comandos, o al **24** para ver todo lo que pasa sin molestar a la web. Así puedes depurar mientras la web y Claude usan el 23.

## 3. Con la web del portátil (Surface/PC)

- En la red del móvil: `python tools/clio_web.py --auto bridge:auto`. Busca el puente solo (`clio-kline.local`, aviso UDP o 192.168.4.1).
- En la red CLIO-KLINE: en la web elige «Puente ESP» con la dirección `tcp:192.168.4.1:23`.
- La pestaña Tablero → Consola acepta los comandos del puente (`STATUS`, `STATS`, `TEST LINE`, `LOGDUMP`, `WIFI…`).
- Claude los usa con la herramienta `send` del MCP y lee el log con `serial_log`.

## 4. En el coche

Con el contacto puesto, el motor parado y el cargador conectado:
`INIT FAST 7A` → `SEND 10C0` → `SEND 2180`. Si no contesta, prueba `INIT SLOW 7A` o `TIMING P2MAX 300`.

## Comandos

| Comando | Qué hace |
|---|---|
| `PING`, `VERSION`, `HELP` | básico |
| `STATUS` | enlace, UCE, keybytes, wifi, memoria libre |
| `STATS [RESET]` | contadores: tx, rx, timeouts, checksum, eco, inits, keep-alive |
| `INIT FAST [ecu] [intentos]` / `INIT SLOW [ecu]` | wake-up de 25 ms + StartCommunication / dirección a 5 baudios |
| `SEND <hex>` | petición sin cabecera ni checksum (solo `10C0 3E 21 17 18 1A`) |
| `ECU <hex>` | cambia de dirección (luego `INIT`) |
| `KEEPALIVE ON [ms]` / `OFF` | `3E` automático; si fallan 3 seguidos: `EVT LINK LOST` |
| `SNIFF ON/OFF` | escucha pasiva: `RAW <hex> cs=ok/mal` |
| `SIM ON/OFF` | UCE simulada sin línea (7A, 26, 28) |
| `TEST LINE` / `TEST ECHO [n]` | diagnóstico del hardware sin centralita |
| `TIMING [CLAVE valor]` | P1MAX P2MAX P2EXT P3MIN P4 W5 TINIL TWUP |
| `BAUD n`, `LOG 0-3`, `LOGDUMP` | velocidad, detalle del log (2 = con eco) y últimas 40 líneas |
| `CONFIG`, `SET clave valor`, `SAVE`, `FACTORY`, `REBOOT` | ajustes en la EEPROM |
| `WIFI ssid clave` / `WIFI OFF`, `NET`, `SCAN` | wifi del móvil, estado de la red y redes cercanas |

Formato de salida: `PREFIJO micros texto`. Cada comando termina con **una** línea `OK` o `ERR`. Lo asíncrono va con `EVT`, `DBG`, `RAW` e `INFO`, así la web nunca lo confunde con la respuesta.

Claves de `SET`:
- Wifi: `STA_SSID`, `STA_PASS`, `AP_SSID`, `AP_PASS`, `HOST` y `AP_ALWAYS` (0 = apagar la red propia si hay wifi del móvil).
- Línea: `ECU`, `TESTER`, `BAUD`, `RETRIES`, `LOG`, `ECHO` (0 si el transceptor no devuelve eco), `AUTOKA` y `KA_MS`.
- Tiempos: los mismos de `TIMING`.

## Probar sin placa (en el PC)

```
python -m platformio run -d firmware -e native
firmware/.pio/build/native/program --port 2323     (opciones: --noecho --deaf --stuck-low)
python tools/clio_web.py   →  Puente ESP, tcp:127.0.0.1:2323
python tools/test_clio_web.py   (incluye la prueba de la web contra este firmware)
```

## Problemas típicos

| Síntoma | Causa probable |
|---|---|
| No aparece la wifi CLIO-KLINE | Sin 3,3 V o el ESP-01 está mal enchufado. EN y RST deben ir a 3,3 V. |
| `TEST LINE` reposo=0 | Sin 12 V en el pull-up R10, un corto en la K o el LM339 sin alimentar |
| `TEST LINE` tx0->1 | GPIO2 no está a 0 (el firmware lo pone a 0 al arrancar), D2 está al revés o hay un fallo en R7/comparadores |
| `TEST ECHO` 0/8 con la línea bien | RX del ESP sin la R4 de pull-up o el comparador de RX mal (R1/R2/R3) |
| `ERR NOECHO` en SEND | Lo mismo que el anterior: lo enviado no vuelve |
| `ERR TIMEOUT` en INIT | Contacto quitado, dirección incorrecta, otro tester conectado; prueba `INIT SLOW` o `TIMING P2MAX 300` |
| `EVT eco distinto` | Colisión con otro tester (Renolink/ELM conectado a la vez) o ruido |
| Se reinicia al conectar el wifi | Falta C1 (470 µF) junto al ESP-01 o el buck da poca corriente |
