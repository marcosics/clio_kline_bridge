# Puente línea K con ESP-01 + LM339N (sin L9637D)

**Dibujos para imprimir** (en `docs/img/`): `esquemas_imprimir.pdf` (A4 apaisado, 3 hojas), y por separado `protoboard_esp01_lm339.png`, `obd_pines.png` y `pinout_lm339_esp01.png`. Se regeneran con `python docs/img/gen_esquemas.py && node docs/img/render.js`.

Firmware: `pio run -e esp01 -t upload` (ya compila, **no hay que cambiar nada**: la lógica es NO invertida y GPIO2 a nivel bajo habilita el TX).

## 1. Esquema general

```
 COCHE (toma OBD)                PLACA                                   PC / móvil
 ┌──────────┐
 │ 16 +12V  ├──F1 1A──D1 1N4007──┬── +12P ──► regulador ──► +3V3 ──► ESP-01, LM339
 │  7  K    ├────────────────────┼─────────────── K ◄──► LM339 ◄──► ESP-01 ~~ Wi-Fi "CLIO-KLINE" ~~ clio_web.py
 │  4  masa ├──┬─────────────────┼── GND                                          (tcp:192.168.4.1:23)
 │  5  masa ├──┘                 │
 └──────────┘                    └── R10 1k ── K   (pull-up de la línea K)
```

## 2. Patillaje de las piezas

### LM339N (DIP-14, visto desde arriba, muesca arriba)
```
            ┌───U───┐
  OUT2   1 ─┤       ├─ 14  OUT3
  OUT1   2 ─┤       ├─ 13  OUT4
  VCC    3 ─┤LM339N ├─ 12  GND
  IN1-   4 ─┤       ├─ 11  IN4+
  IN1+   5 ─┤       ├─ 10  IN4-
  IN2-   6 ─┤       ├─  9  IN3+
  IN2+   7 ─┤       ├─  8  IN3-
            └───────┘
```
Salidas en colector abierto (aguantan 36 V): por eso puede tirar de la línea K a masa aunque se alimente a 3,3 V.

### ESP-01 (8 pines)
```
   ┌──────────────────────────┐
   │ antena   [chip]          │   fila 1:  GND   GPIO2  GPIO0  RX(GPIO3)
   │                  o o o o │   fila 2:  TX(GPIO1) EN(CH_PD) RST  VCC
   │                  o o o o │
   └──────────────────────────┘
```
GND y TX están en la misma columna; VCC y RX, en la otra punta. **Comprobación:** GND tiene continuidad con la tapa metálica del ESP8266. VCC es el pin en diagonal opuesto a GND. Solo 3,3 V: 5 V lo rompe.

### Toma OBD del coche (hembra, vista de frente)
```
   ┌─────────────────────────────────┐
    \  1   2   3  [4] [5]  6  [7]  8 /      4 = masa chasis
     \ 9  10  11  12  13  14  15 [16]/      5 = masa señal
      └─────────────────────────────┘       7 = línea K
                                           16 = +12 V permanente (con fusible del coche)
```
En el Clio II está en la consola central, delante de la palanca (detrás de la tapa/cenicero).

## 3. Alimentación (+3V3)

El ESP-01 pide picos de ~300 mA con Wi-Fi: **no** sacar 3,3 V de 12 V con un AMS1117 solo (se quema).

```
Opción A (recomendada, ~1 €): mini buck MP1584 / LM2596 ajustado a 3,3 V ANTES de conectar el ESP
  +12P ──[IN+ buck OUT+]── +3V3
  GND  ──[IN-      OUT-]── GND

Opción B (con lo de casa): cargador USB de mechero + regulador 3,3 V (AMS1117 / módulo)
  mechero ─ cargador USB ─ cable USB cortado: rojo 5V ─► AMS1117 IN, OUT ─► +3V3
                                              negro   ─► GND  (unirlo a la masa OBD 4/5)

En los dos casos, junto al ESP-01:   +3V3 ──┬── C1 470 µF ──┬── GND
                                            └── C2 100 nF ──┘
```
F1 (fusible 1 A) y D1 (1N4007, protege de inversión de polaridad) siempre. Si tienes un TVS de 18 V (P6KE18A / SMBJ18A), ponlo entre +12P y GND y otro entre K y GND.

## 4. Interfaz línea K con el LM339

```
                         +12P
                          │
                         R10 1k (¼ W)
                          │
 OBD 7 ───────────────────┴────────────────┬─────────────────────────── nodo K
                                           │
 ══ RECEPCIÓN (K → ESP RX) ══              │
                                          R1 68k
                                           │                +3V3
                                           ├──► pin 5 IN1+   │
                                          R2 10k            R4 10k
                                           │                 │
                                          GND    pin 2 OUT1 ─┴──────► ESP RX (GPIO3)
        +3V3 ── R3 47k ──┬──► pin 4 IN1-
                         R11 10k          umbral: K > 4,5 V = "1"
                         │
                        GND

 ══ TRANSMISIÓN (ESP TX → K) ══
        +3V3 ── R5 10k ──┬──► pin 6 IN2-  y  pin 8 IN3-   (referencia 1,65 V)
                         R6 10k     └──► pin 10 IN4- (comparador 4 sin usar)
                         │
                        GND
 ESP TX (GPIO1) ── R7 10k ──┬──► pin 7 IN2+  y  pin 9 IN3+
                            │
 ESP GPIO2 ──►|── D2 1N4148 ┘   (ánodo en GPIO2; bloquea el TX mientras arranca)

 pin 1 OUT2 ──┬────────────────────────────────────────────────────── nodo K
 pin 14 OUT3 ─┘   (dos salidas en paralelo: ~12 mA para bajar la K con R10 de 1k)

 ══ RESTO DEL LM339 ══
 pin 3 VCC ── +3V3 (+ 100 nF a masa pegado al chip)
 pin 12 GND ── GND
 pin 11 IN4+ ── GND ; pin 13 OUT4 sin conectar
```

Cómo funciona:
- TX a 0 → IN+ < 1,65 V → salidas a masa → K baja. TX a 1 → salidas abiertas → R10 sube la K a 12 V. Sin inversión.
- Al arrancar, el ESP-01 saca basura por TX: GPIO2 está alto (pull-up R8) y, a través de D2, mantiene IN+ alto, así que la K no se mueve. El firmware pone GPIO2 a 0 cuando ya está listo.
- Si se va la alimentación de 3,3 V, el LM339 se apaga y suelta la K: no bloquea la línea al coche.
- El ESP recibe el eco de lo que envía (normal en la línea K; el firmware lo descarta).

## 5. Conexiones del ESP-01

```
 ESP-01         a
 VCC        ── +3V3
 GND        ── GND
 EN (CH_PD) ── +3V3 directo
 RST        ── +3V3 directo
 GPIO0      ── +3V3 directo   (alto al arrancar = arranque normal)
 GPIO2      ── R8 10k ── +3V3    y al ánodo de D2
 TX (GPIO1) ── R7 → LM339 pines 7/9
 RX (GPIO3) ── LM339 pin 2 (con R4 a +3V3)
```

## 6. Lista de piezas

| Ref | Valor | Nota |
|---|---|---|
| U1 | LM339N | el que tienes |
| U2 | ESP-01 | el que tienes |
| R10 | 1 kΩ ¼ W | pull-up K. Si con la K baja mides >1,5 V, cambia a 1,5 kΩ |
| R1 | 68 kΩ | divisor K |
| R3 | 47 kΩ | referencia RX |
| R2, R4-R8, R11 | 10 kΩ | 7 uds |
| D1 | 1N4007 | polaridad |
| D2 | 1N4148 | puerta TX (si no tienes, prueba sin ella: solo hay basura en la K al arrancar el ESP) |
| F1 | 1 A | portafusibles de cable o fusible de coche |
| C1, C2, C3 | 470 µF 10 V, 100 nF ×2 | |
| Regulador | buck 3,3 V o cargador USB + AMS1117 | |

## 7. Sin conector OBD macho

Opciones, de mejor a peor:
1. **Pines con cable rígido de instalación de casa (1,5 mm²)**: pelar 1 cm, encaja justo en los contactos hembra de la toma. Soldar cada uno a su cable, aislar con termorretráctil y sujetar los 4 juntos con cinta o un trozo de plástico. Solo pines **4, 5, 7 y 16**.
2. **Por detrás de la toma**: soltar la toma de la consola y pinchar con pines Dupont macho por la parte de los cables (sin pelarlos).
3. Directo a la UCE (A-B4) y batería: no, solo si lo demás falla.

Orden al conectar: masas (4, 5) → K (7) → **+12 V (16) el último**, con F1 puesto. Un pin 16 tocando masa funde el fusible del coche.

Los Dupont de 0,64 mm bailan en la toma OBD: no usarlos por delante sin engordarlos.

## 8. Grabar el ESP-01

Con el adaptador USB-ESP01 (CH340), **fuera de la placa**:
- Si el adaptador no tiene botón de programación: puente GPIO0-GND al enchufarlo, y quitarlo después.
- `cd firmware && pio run -e esp01 -t upload`

## 9. Pruebas antes del coche (banco)

1. Sin ESP ni LM339: comprobar +3V3 con el polímetro (3,2-3,4 V).
2. Montar todo y alimentar +12P con una pila de 9 V o una fuente de 12 V.
3. K en reposo ≈ tensión de la pila. Conectar el móvil/PC al Wi-Fi `CLIO-KLINE` (clave `clio1234`).
4. `python tools/clio_web.py` → backend `bridge`, dirección `tcp:192.168.4.1:23`. O a mano: `telnet 192.168.4.1 23` → `PING`.
5. `SEND 3E` sin UCE: debe salir `ECHO …` y luego `ERR TIMEOUT` (TX y RX funcionan).
6. `INIT FAST 7A` con el polímetro en K: baja un instante.

## 10. En el coche

Contacto puesto, motor parado, cargador de batería si se alarga. Con la web: `connect bridge tcp:192.168.4.1:23` → `INIT FAST 7A` → `10C0` → `2180`. Solo lectura (el firmware bloquea las escrituras).
