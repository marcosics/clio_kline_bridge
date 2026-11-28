# Estado de todo lo pedido (26/11/2026)

Leyenda: ✅ hecho y probado con el simulador · 🟡 hecho, falta el coche o un dato tuyo · ⏳ pendiente

| Pedido | Estado | Dónde / qué falta |
|---|---|---|
| Identificar el cable «SX» (ELM/OBDLink/vLinker) | 🟡 | `clio_kline.py probe`. Falta ejecutarlo con el cable. |
| Puente con lo de casa (ESP-01 + LM339N) | 🟡 | Esquema y dibujos en `docs/esquema_ESP01_LM339.md` y `docs/img/`. Falta montarlo y probarlo en banco. |
| Firmware 2.x completo (init rápido/5 baudios, eco, tiempos, pruebas de hardware, wifi del móvil, OTA, web del ESP) | 🟡 | `firmware/LEEME.md`. Probado en el PC contra la web (línea K virtual). Falta grabarlo en tu placa. |
| Pruebas ESP con PlatformIO | 🟡 | `firmware/`: 5 entornos compilan. Falta grabarlo y probarlo con el L9637D. |
| ECU simulada para probar sin coche | ✅ | Simulador en la web y `SIM ON` / `esp32_ecusim` en el firmware. |
| Una sola web con fallos, datos y configuración | ✅ | Pestañas Claude en vivo, Tablero, Fallos, Configuración y Aprendizaje. |
| Fallos (leer) | ✅ | 17/18, con el nombre de la base DDT si está cargada. |
| Fallos (borrar) | — | Solo a mano con DDT4ALL/Renolink (regla de CLAUDE.md). |
| Todas las variables en el tablero | 🟡 | Salen de la base DDT o de lo aprendido. Sin base, hay que aprenderlas en el coche. |
| Varias centralitas: inyección, ABS, UCH (luces, llaves), airbag, cuadro | 🟡 | Cambiar UCE, «Probar todas», fast init o 5 baudios. Falta ver cuáles responden en tu coche. |
| Modificar parámetros | — | La web enseña qué existe; los cambias tú a mano con DDT4ALL, con copia y cargador. |
| Base de datos existente (DDT4ALL/DDT2000) | 🟡 | Soportada y con decodificación igual que DDT4ALL. **No es pública**: falta tu `ddt/ecu.zip`. |
| Aprendizaje que hace todo solo | ✅ | «Exploración automática» (sin IA) y «Claude en vivo»: Claude lee, explora, te pide acciones en la web, guarda lo aprendido e informa. |
| Que la IA lo lea y lo pruebe todo | ✅ | MCP `clio-kline` (23 herramientas) a través de la misma web. Probado de punta a punta. |
| Recomendaciones y posibles problemas | 🟡 | En el informe de «Claude en vivo» (`informes/`). Necesita datos reales. |
| Llaves / antiarranque | 🟡 | Solo leer el estado (UCH 26). Registrar llaves: Renolink/CLIP con el código del coche. |
| Luces | 🟡 | Filtro «Luces» de la UCH. Depende de la base DDT y de que la UCH responda. |
| Sniffer y log serie del micro | 🟡 | `SNIFF ON` y «Log serie», solo con el puente ESP. |
| Línea L | — | No hace falta: el diagnóstico del Clio II va por la K (pin 7), también el init a 5 baudios. |
| Modo coche: registro continuo, anomalías y autodescubrimiento | ✅ | `MODO_COCHE.md`, `arrancar_coche.bat`. Probado con el simulador (con ABS simulado). Falta el coche. |
| Panel que diseña la IA y memoria de la IA | ✅ | Pestaña Panel (`tools/ui_layout.json`), herramientas `ui_page`/`memory_add`. |
| IA automática y chat en el coche | 🟡 | `--ia-auto 30` y chat en Modo coche. Falta probarlo con Claude real en el coche. |
| ESP en el hotspot del móvil | 🟡 | Firmware compila en los 5 entornos. Falta poner tu wifi en `[movil]` y probarlo. |
| Ordenador de a bordo (consumo, autonomía, temperaturas, rail, turbo) | ⏳ | Fórmulas en CLAUDE.md §7. Falta identificar el caudal (PR017) y la velocidad en el coche. |
| Pantalla ESP32 y Android | ⏳ | Fase 3, cuando tengamos las variables. |
| Programar el ESP desde la web | ⏳ | Pendiente. Por ahora `python -m platformio run -d firmware -e esp32 -t upload`. |
| Regulador de fábrica | ⏳ | Cablear A2/C3/D2/D3/C4, configurar CF582 con DDT4ALL y comprobar LC036. Filtro «Regulador» en Configuración. |
| Seguridad (nunca escribir en la ECU automáticamente) | ✅ | Lista blanca en el firmware, la web y el MCP. Quitada la escritura del MCP antiguo. |

## El día del coche
1. Contacto ON, motor parado, cargador conectado.
2. `python tools/clio_web.py` → «ELM», tu `COMx` → Conectar.
3. Dímelo aquí, o pulsa «Claude en vivo → Empezar» y responde a lo que pida en la banda amarilla.
