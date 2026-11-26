# Pruebas

## 0. Sin hardware (PC)
```
python tools/test_clio_web.py
python tools/clio_web.py          # http://localhost:8080 → «Simulador» → Conectar
```
Pestañas:
- **Tablero:** variables en vivo.
- **Fallos:** averías e identificación.
- **Configuración:** centralitas y base DDT4ALL.
- **Aprendizaje:** grabación con marcas, análisis, variables, bytes, escaneo y consola.

Claude usa lo mismo con el MCP `clio-kline` (`.mcp.json`), que pasa por la web. Por eso la web tiene que estar arrancada.

## 1. Delante del coche (contacto ON, motor parado, cargador)
1. Conecta el cable y busca el COM en el Administrador de dispositivos.
2. `python tools/clio_kline.py --port COM5 probe` (con la web cerrada: un solo programa por puerto).
3. `python tools/clio_web.py` → backend «ELM», `COM5`, los baudios que dio `probe`, UCE 7A, fast init → Conectar.
4. Dile a Claude «estoy delante del coche». A partir de ahí Claude:
   - lee la identificación, las averías y los LIDs;
   - prueba las otras centralitas;
   - te guía con las marcas de aprendizaje (freno, embrague, pedal…) y guarda lo aprendido.
5. Si el ELM no hace el fast init, pasa al puente ESP32 (sección 2).

## 2. Puente ESP32
```
python -m platformio run -d firmware -e esp32 -t upload
python -m platformio device monitor -d firmware -e esp32
```
Sin transceptor: `SIM ON`, `INIT FAST 7A`, `SEND 2180`, `SEND 2E0101` (→ `ERR BLOCKED`).
Web: backend «Puente ESP», `COMx` (115200) o `tcp:192.168.4.1:23` (Wi-Fi `CLIO-KLINE`, clave `clio1234`). Cierra el monitor antes.

Banco de pruebas:
- Graba el otro ESP32 con `-e esp32_ecusim`.
- Une los dos L9637D por la línea K (pull-up de 510 Ω a 12 V).
- En el puente: `SIM OFF` y después `INIT FAST 7A`.
