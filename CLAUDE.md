# CLIO KLINE — contexto completo para Claude Code

Documentación de apoyo:
- `docs/traspaso_CLIO_KLINE.md`: pinout de la ECU, montaje del regulador, piezas y fuentes.
- `tools/`: herramientas Python ya hechas (escáner y servidor MCP).

## 0. Cómo trabajar con el usuario (obligatorio)
- Respuestas concisas. Sin texto innecesario y sin explicar cada paso.
- Cuando pida continuar, seguir desarrollando directamente, sin escribir pensamientos ni resúmenes largos.
- Idioma: español.
- Hardware barato y lo que ya tiene en casa. Prioriza la relación calidad-precio y que funcione.
- Lo desarrolla él mismo, por fases. Le gusta construirlo y entenderlo, no solo comprar el kit hecho.
- Seguridad no negociable: nunca escribir en la ECU desde el firmware o el MCP automático. Las escrituras de configuración se hacen a mano con DDT4ALL o Renolink, con copia previa y cargador de batería conectado.

## 1. Vehículo
- Renault Clio II fase 2, 3 puertas, 1.5 dCi **K9K 702**, 60 kW / 82 cv, de 2002 (Valencia, España).
- Versión básica («pelado»):
  - Sin ordenador de a bordo, sin regulador/limitador y sin preinstalación.
  - Cuadro con solo km totales, parcial y «oil check».
  - Pedal de acelerador electrónico (fase 2).
- Radio Android de 9" (AliExpress, marco específico del Clio) con Torque instalado.

## 2. Objetivos (por prioridad)
1. **Herramienta de desarrollo con IA:**
   - Claude lee y escribe la línea K en tiempo real: envía tramas, recibe respuestas, hace de sniffer y lee el log serie del micro.
   - Lo usa para entender los datos de la ECU y diagnosticar averías.
   - Se apoya en las bases de datos de la comunidad (DDT4ALL/DDT2000, pyren).
2. **Ordenador de a bordo propio:** consumo instantáneo y medio, autonomía, temperaturas, presión del rail, turbo, etc., además de información que el coche no trae.
   - Pantalla pequeña con ESP32.
   - Más adelante, integrado en la radio Android.
3. **Regulador de velocidad:**
   - Vía preferida: la función de fábrica de la ECU (cablear A2, C3, D2, D3 y C4; ver docs).
   - La pantalla propia mostraría la velocidad fijada, porque su cuadro no tiene testigo ni «SET».
   - Mandos: palanca o botones (+, −, R, 0) mediante una red de resistencias entre D2 y D3.
   - Alternativa: kit de AliExpress de ~25 €.
   - **No** diseñar un regulador propio que genere la señal del pedal.
4. Diagnóstico y configuración por OBD / línea K con el material que tiene.

## 3. Material disponible
- Cable USB con la etiqueta «OBDLink SX» o «Vlinker SX», probablemente un clon ELM327 USB/FTDI tipo Renolink. **Verificar con `ATI` y `STI`.**
  - OBDLink SX real: STN, baudios 115200, RTS/CTS.
  - vLinker FS: 38400 por defecto.
  - Clon: ELM v1.5/v2.1.
- ESP8266 **ESP-01** (8 pines) en casa. Más adelante podría pasar a ESP-12/Wemos D1 mini o ESP32.
- Opción barata: ELM327 Bluetooth (los v2.1 baratos suelen ir mal con la línea K; los buenos llevan PIC18F25K80).
- Software:
  - Renolink.
  - Torque en el Android.
  - PC con Windows.
  - Claude Desktop / Claude Code.
  - Claude in Chrome.
- Falta comprar:
  - Transceptor de línea K **L9637D** (<1 €), o en su defecto un circuito de transistores.
  - Convertidor buck de 12 a 5/3,3 V.
  - Conector OBD macho.

## 4. ECU: Delphi DDCR (no confundir con la DCM1.2 del Clio III)
- Ubicación: detrás de la batería, con 3 conectores. El derecho (A, 32 vías) es el lado vehículo.
- Línea K: ECU A-B4 ↔ pin 7 de la toma OBD. La ECU y la UCH se comunican por CAN en A3/A4 (antiarranque). **No tocar.**
- Referencias posibles para el 82 cv: 8200212348 / HOM8200222917 (R0410C039A, 80945A) y 8200212351 (80931H/80944C). **Leer la del coche con `2180`.**
- Regulador:
  - El manual Renault NT 3845A (DDCR, programa BE) menciona CF582 (configurar regulador/limitador) y LC036 (leer si está configurado).
  - En dCi de antes de 2003 a veces hizo falta una actualización de la ECU en Renault.
  - Si con el cableado sale «SET», la función está activa.
  - Prueba barata: puentear +12 V STOP a A2 o C3.

## 5. Protocolo de la línea K (confirmado en Renault con ECU 0x7A)
- ISO 14230 (KWP2000), 10400 baudios, 8N1. Dirección de la ECU **0x7A**, tester **0xF1**.
- **Fast init:** K a nivel bajo 25 ms, alto 25 ms, y después StartCommunication. El 5-baud init falla.
- Secuencia ELM probada (log de pyClip):
  ```
  ATSP5  ATSH817AF1  ATSW96  ATWM817AF13E  ATAL  ATFI  ATAT1
  10C0  → 50C0          (sesión Renault)
  2180  → 6180…         (identificación de la ECU)
  ```
- Trama: `[fmt|len][dest][orig][datos][checksum = suma & 0xFF]`. Ejemplo: `82 7A F1 21 A1 AF`.
- Datos en vivo: `21A0`, `21A1`, `21A2`.
  - `21A1` incluye rpm, consigna de rpm, pedal, temperatura del agua, batería, presión del rail y consigna, A/C y bits de avería.
  - La temperatura del aire está en `21A2`, byte 7.
  - **Los valores de 16 bits van en little endian:** DDT4ALL los decodifica mal en la DDCR y pyren bien.
- Averías: lectura con `17` / `18`; borrado con `14` (solo a mano).
- Keep-alive `3E` cada ≤2 s. Timings: P2 25-50 ms, P3 ≥55 ms. Respuesta `7F xx 78` = respuesta pendiente (seguir esperando).
- La línea K es half-duplex y se recibe el eco de lo enviado, que hay que descartar.
- Un solo tester en la línea a la vez.
- Pendiente de localizar en el XML/JSON de DDT4ALL (`DDCR_*`, base `ecu.zip` v5): velocidad del vehículo, contactores de freno y embrague, estado del regulador y velocidad fijada.

## 6. Seguridad (firmware y PC)
- Permitidos: `10 C0`, `3E`, `21`, `17`, `18`, `1A`.
- Bloqueados siempre: `34`-`37`, `11`, `10 85`, `31`, `27`, `3B`, `2E`, `14`.
- Todo se registra en `logs/*.jsonl`.

## 7. Ordenador de a bordo: cálculos
- Caudal (PR017, mg por inyección y cilindro) → L/h = mg × 4 × (rpm/2) × 60 / 10⁶ / 0,835.
- L/100 km = L/h × 100 / v. Por debajo de 5 km/h mostrar L/h.
- Medio = ∫litros / ∫km con el Δt real de cada muestra. Autonomía = litros restantes (repostados que introduce el usuario) / consumo medio.
- Comprobación: al ralentí debe salir ~0,6-1,1 L/h. Calibrar con repostajes (error esperado de unos pocos % a ~10 %).
- Velocidad: de la ECU si aparece en alguna trama. Si no, por pulsos del captador de velocidad con optoacoplador, calibrado con GPS.

## 8. Arquitectura
```
[ECU 0x7A] ─K─ [transceptor L9637D] ─UART 10400─ [micro] ─USB serie / Wi-Fi TCP─ [PC: MCP → Claude]
                                                         └─ Wi-Fi/BLE ─ [Android 9" / pantalla ESP32]
```
- Fase 1: PC + ELM327 (cable USB o BT) + `tools/clio_mcp.py`. Si el ELM falla con la línea K → fase 2.
- Fase 2: puente propio (opciones de hardware más abajo).
- Fase 3: el ESP32 es el único maestro de la línea K, calcula los datos y los publica por WebSocket/BLE. Pantalla y Android solo muestran.

### Opciones de micro para el puente
| Micro | Línea K | Depuración / PC | Notas |
|---|---|---|---|
| ESP32 (recomendado) | UART2 GPIO16/17 | USB + Wi-Fi | fast init: pasar TX a GPIO 25 ms abajo / 25 ms arriba |
| ESP-01 (el que tiene) | GPIO1 TX / GPIO3 RX (su único UART) | **solo Wi-Fi** (TCP :23 + web) | Al arrancar saca basura por TX a 74880 baudios: cortar el TX del transceptor con un transistor por GPIO2 hasta que esté listo. GPIO0/2 en alto al arrancar. Se flashea con un adaptador USB-ESP01 (CH340). |
| ESP-12 / D1 mini | `Serial.swap()` → GPIO13/15 | USB + Wi-Fi | mejora natural del ESP-01 |
| Arduino Uno | AltSoftSerial 8/9 | USB | solo para pruebas, sin Wi-Fi |

### Interfaz eléctrica (nunca conectar el pin 7 directamente al micro)
- **L9637D:**
  - Vs = +12 V OBD.
  - LI ← TX del micro.
  - RO → RX del micro, con pull-up a 3,3 V.
  - K con pull-up de 510 Ω a 12 V.
- **Con lo que tiene (LM339N + ESP-01):** esquema completo en `docs/esquema_ESP01_LM339.md` (lógica no invertida, sin cambios de firmware).
- **Alternativa discreta:**
  - TX: micro → 1 kΩ → NPN con el colector a la K.
  - RX: K → 10 kΩ → NPN con pull-up de 10 kΩ a 3,3 V.
  - Las dos señales quedan invertidas: invertir en el firmware.
- Protección: TVS de 18 V en la K y en +12 V, fusible, y buck de 12 a 5/3,3 V (no usar un AMS1117 directo desde 14 V).
- Toma OBD: 7 = K, 16 = +12 V, 4/5 = masa.

### Protocolo de comandos del firmware 2.x (texto, igual por USB, telnet :23 y la página web del ESP)
Referencia completa y guía de depuración: `firmware/LEEME.md`. Núcleo portátil en `firmware/src/core/`, plataformas en
`firmware/src/platform/` (ESP8266/ESP32, Uno y `native` = mismo firmware en el PC con línea K virtual, usado por las pruebas).
```
PING · VERSION · HELP · STATUS · STATS [RESET]
INIT FAST [ecu] [intentos] | INIT SLOW [ecu]   -> OK INIT 7A kb=EF8F | ERR INIT <motivo con pista>
SEND <hex sin checksum>   -> TX <trama> / RX <trama> / OK SEND | ERR TIMEOUT|CHECKSUM|INCOMPLETE|NOECHO|BLOCKED
ECU <hex> · KEEPALIVE ON [ms]|OFF · SNIFF ON|OFF (RAW <hex> cs=ok) · SIM ON|OFF
TEST LINE · TEST ECHO [n]      -> diagnóstico del hardware sin UCE
TIMING [clave valor] · BAUD · LOG 0-3 · LOGDUMP · CONFIG · SET · SAVE · FACTORY · REBOOT
WIFI ssid clave | WIFI OFF · NET · SCAN       (ESP: wifi del móvil guardado en EEPROM)
```
Cada comando termina con UNA línea `OK`/`ERR`; lo asíncrono va con `EVT`, `DBG`, `RAW`, `INFO`. Prefijo + µs + texto.
ESP: puerto 23 control (un cliente), 24 monitor de solo lectura, 80 página de diagnóstico, OTA (`-e esp01_ota`).

### Web y servidor MCP (hecho)
- `tools/clio_web.py` es el **único tester** de la línea K: backends `sim`, `elm` y `bridge`. Pestañas: Tablero, Fallos, Configuración y Aprendizaje.
- `tools/clio_mcp.py` es un cliente HTTP de la web; se registra en `.mcp.json`. Herramientas:
  - conexión: `connect`, `select_ecu`, `ecu_scan`, `status`
  - lecturas: `ident`, `read_dtc`, `live`, `scan_lids`, `send`, `serial_log`
  - aprendizaje: `learn_start`, `learn_mark`, `learn_stop`, `learn_analyze`, `recordings`
  - tabla local: `decode_get`, `decode_set`
  - base DDT4ALL: `db_status`, `db_search`, `db_read`
  - modo coche: `drive_start`, `drive_stop`, `drive_status`, `drive_summary`, `drive_series`, `events`, `drives`, `analyze_drive`
  - panel y memoria: `ui_get`, `ui_page`, `ui_set`, `memory_get`, `memory_add`
- **Modo coche** (`MODO_COCHE.md`, `tools/clio_drive.py`): registro continuo con reconexión, otras UCE cada N s,
  eventos (avería, anomalía, byte que despierta, comunicación), autodescubrimiento (contadores, bits, correlaciones),
  panel `tools/ui_layout.json` que diseña la IA y memoria `tools/ia_memoria.md`. IA automática con topes diarios
  (`--ia-auto MIN`) y chat que continúa la sesión. El ESP se une al hotspot del móvil (`[movil]` en platformio.ini)
  y se descubre por mDNS `clio-kline.local` o UDP `CLIO?` al puerto 4210.
- Lo aprendido se guarda en `tools/ddcr_decode.json`. La base DDT4ALL va en `ddt/ecu.zip` (no es pública; ver `ddt/LEEME.md`).
- Pruebas: `python tools/test_clio_web.py`. Guía delante del coche: `PRUEBAS.md`.
- Leer el puerto en directo también con `pio device monitor` o `python -m serial.tools.miniterm`.

## 9. Pasos de desarrollo
1. Identificar el cable (`ATI`/`STI`) y probar `tools/clio_kline.py --port COMx info`.
2. Si responde: `scan` → `learn` (freno, embrague) → capturar `21A0/A1/A2` al ralentí y en marcha. Comparar con DDT4ALL/pyren en otra sesión.
3. Proyecto PlatformIO con los entornos `esp01`, `esp32`, `d1mini` y `uno`, y una HAL común.
4. Firmware con **modo simulador de la ECU** (`81→C1`, `10C0→50C0`, `21A1→61A1…`) para probar sin el coche. Tests en el PC.
5. Banco de pruebas: micro + transceptor + 12 V + un segundo micro haciendo de ECU simulada. Verificar el fast init con SNIFF o un analizador lógico.
6. En el coche (contacto, motor parado, cargador): `INIT FAST 7A` → `10C0` → `2180`.
7. Generar desde el JSON de DDT4ALL (`DDCR_*`) tablas de decodificación en C++ y Python, con tests sobre las tramas capturadas.
8. Ordenador de a bordo en ESP32 + pantalla (p. ej. ESP32-S3 + LVGL) y después publicar a Android (RealDash o una app web por WebSocket).

## 10. Proyectos de referencia
- muki01/OBD2_KLine_Library y muki01/OBD2_K-line_Reader (fork en español: dewasha40): fast init, eco y checksum en ESP32/ESP8266.
- erdemerciyas/K-line-Ecu: ESP32-S3 + L9637D + LVGL con pantalla redonda.
- iwanders/OBD9141.
- Sketch de arduino.ru (MaksVV): Renault 0x7A, fast init, `10C0`, `2180`.
- Dante383/gkbus: KWP2000 en Python.
- cedricp/ddt4all, pyren: decodificación y bases de datos.
- uholeschak/ediabaslib (CanAdapterElm): firmware abierto para reflashear clones con PIC18F25K80.
- SavvyCAN y los emuladores ELM de ESP32 (WiCAN, EQM_OBDWEB) son **solo CAN**: no sirven.

## 11. Pendiente / dudas abiertas
- Identidad real del cable y si hace fast init con la DDCR.
- Referencia de la ECU del coche, y si CF582/LC036 aparecen y se pueden configurar con DDT4ALL.
- A2/C3: las fuentes discrepan sobre cuál es regulador y cuál limitador.
- Confirmar C4 = embrague con el manual EC-K9K.
- Tramas y offsets de velocidad, contactores y velocidad fijada.
- Ordenador de a bordo de fábrica: requiere el cuadro de un Clio II fase 2 con ODB + el mando del limpia con botón. Opcional frente a la pantalla propia.
- Legalidad: un regulador no de fábrica = reforma 2.8 (ITV). La función de fábrica con piezas Renault es más defendible; consultar con la ITV.
