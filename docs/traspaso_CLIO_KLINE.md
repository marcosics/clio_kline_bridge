# CLIO KLINE – Documento de traspaso COMPLETO
Renault Clio II fase 2, 3 puertas, 1.5 dCi K9K 702, 60 kW / 82 cv, de 2002 (Valencia)
Última actualización: 19/11/2026. Recoge todo lo hablado en el chat anterior para seguir en el chat «CLIO KLINE».

---------------------------------------------------------------------
## 0. CONTEXTO DEL USUARIO Y OBJETIVOS
- El coche viene «pelado»: sin ordenador de a bordo, sin regulador/limitador y sin preinstalación. El cuadro solo muestra kilómetros totales, parcial y «oil check».
- Objetivos:
  1. Montar el regulador/limitador de velocidad de fábrica (el que lleva la propia centralita), no el de la radio.
  2. Tener ordenador de a bordo (consumo, autonomía…), aunque sea fuera del cuadro.
  3. Conocer el pineado completo de la centralita y qué funciones tiene.
  4. Diagnóstico y configuración por OBD / línea K con lo que ya tiene.
  5. Proyecto propio con ESP32 (u otro micro) por línea K: pantalla y/o regulador propio. Antes ya valoró un kit de crucero de AliExpress (~25 €, con palanca) como alternativa y un proyecto ESP32 con pantalla por OBD de GitHub.
- Material que tiene: un cable USB rojo transparente con la etiqueta «OBDLink SX» (en realidad un clon ELM327 USB/FTDI tipo «Renolink»), el software Renolink, Torque en el Android del coche (radio Android de 9"), un PC con Windows y la extensión Claude in Chrome.
- Preferencias: respuestas concisas, sin explicar cada paso; cuando pide continuar, seguir desarrollando directamente.

---------------------------------------------------------------------
## 1. CENTRALITA (ECU)
- Modelo: **Delphi DDCR** (Delphi Diesel Common Rail), también llamada «DCR» o «Lucas/Delphi DCR». Es la del K9K de primera generación (Clio II 2001-2005, Kangoo, Scénic I…).
- Referencias en la etiqueta: Renault **8200xxxxxx** (ej. 8200180595, 8200206670, 8200212351, 8200212348, 8200303619), homologación **HOM8200129063 / HOM8200222917**, Delphi **R0410C…** (ej. R0410C034A) o **809xx** (ej. 80925M, 80925E, 80944C, 80945A, 80944H). Para buscar recambios o pineado, usar la 8200 de la etiqueta del coche.
- No confundir con la **Delphi DCM1.2** (K9K posterior, Clio III 2005+): otros conectores y otro pineado.
- Ubicación: detrás de la batería. Tres conectores; el de la derecha (junto a la torreta del amortiguador) es el lado vehículo, el que se usa para el regulador.
- Diagnóstico: **línea K** (pin 7 de la toma OBD), ISO 9141 / KWP2000 (ISO 14230). No es CAN de diagnóstico. Entre la ECU y la UCH sí hay CAN (antiarranque).

---------------------------------------------------------------------
## 2. PINOUT DE LA DELPHI DDCR K9K
Fuente principal: revista técnica del Renault Scénic, «Calculateur d'injection diesel : Branchement», K9K Delphi DDCR (https://www.infoscenic.com/calculateur_d_injection_diesel_branchement-157.html). Las imágenes de los conectores están en https://www.infoscenic.com/images/books/95/5/index.33.gif, .34.gif y .35.gif (no se pudieron descargar). Mismo sistema que el Clio II, y coincide con los pines que usan los montajes de ClubClio (A2, C3, D2, D3, C4).

### Conector A – 32 vías (lado vehículo)
| Pin | Función |
|---|---|
| H1 | no utilizada |
| H2 | señal del pedal del acelerador, pista 1 |
| H3 | masa del pedal, pista 1 |
| H4 | masa |
| G1 | + después de contacto (unidad de protección y conmutación, UPC) |
| G2 | alimentación del pedal, pista 1 |
| G3 | no utilizada |
| G4 | masa |
| F1 | no utilizada |
| F2 | alimentación del pedal, pista 2 |
| F3 | señal del pedal, pista 2 |
| F4 | masa del pedal, pista 2 |
| E1-E3 | no utilizadas |
| **E4** | **contacto de freno (stop), contacto de cierre** |
| D1 | + después de contacto (UPC) – otra fuente lo da como +APC por el fusible F5 de 15 A |
| **D2** | **señal de los mandos del regulador (+ / − / R / 0)** |
| **D3** | **masa de los mandos del regulador** |
| D4 | no utilizada |
| C1, C2 | no utilizadas |
| **C3** | **interruptor del limitador (según la revista); regulador según crossmax** |
| **C4** | **contactor de embrague** (no aparece en la tabla K9K; deducido de la tabla F9Q, donde C4 = pedal de embrague, y de los montajes que funcionan) |
| B1-B3 | no utilizadas |
| **B4** | **línea K de diagnóstico (→ pin 7 de la toma OBD)** |
| A1 | no utilizada |
| **A2** | **interruptor del regulador (según la revista); limitador según crossmax** |
| A3 | CAN LOW → UCH (pin 19 según lemondedudiagauto) |
| A4 | CAN HIGH → UCH (pin 20). **No tocar: antiarranque** |

⚠ A2 y C3: la revista dice A2 = regulador y C3 = limitador; en el montaje que funciona de crossmax es al revés. Si las posiciones del interruptor salen cambiadas, intercambiar esos dos cables.

### Conector B – 48 vías (lado motor)
M4 actuador de caudal · L3 electroválvula EGR · K1 apantallado del acelerómetro · **K2/K3 sonda de temperatura del aire exterior** · J2/J3 temperatura del aire de admisión · H2/H3 temperatura del agua · H4 inyector 4 (−) · G1 masa del acelerómetro · G2/G3 temperatura del gasóleo · G4 inyector 4 (+) · F1 señal del acelerómetro · F2/F3 sensor de régimen (+ y masa) · F4 inyector 3 (−) · E1/E2/E3 sensor de árbol de levas (alim., señal, masa) · E4 inyector 3 (+) · D1/D2/D3 presión del rail · D4 inyector 2 (−) · C1/C2/C3 presión del turbo · C4 inyector 2 (+) · B1/B2/B3 potenciómetro EGR · B4 inyector 1 (−) · A4 inyector 1 (+). No utilizadas: M1-M3, L1, L2, L4, K4, J1, J4, H1, A1-A3.

### Conector C – 32 vías
C3 señal de presión del gas del A/C · C4 alimentación del presostato del A/C · D3 diagnóstico de bujías de precalentamiento · **D4 señal del contacto de stop** · F1 mando del relé de alimentación (UPC) · F2 mando del relé de precalentamiento · G1 masa de potencia 1 · G2 + batería 1 tras relé · G3 masa del presostato A/C · H1 masa de potencia 2 · H2 + batería 2 tras relé. El resto, no utilizadas.

### Funciones aprovechables
- Regulador/limitador: A2, C3, D2, D3, C4 + freno A-E4 / C-D4. La ECU ya trae la función; solo hay que cablearla.
- Sonda de temperatura exterior: B-K2/K3 (puede que el coche no lleve la sonda; el cuadro solo la mostraría si tiene pantalla para ello).
- Aire acondicionado: C-C3/C4/G3.
- Línea K: A-B4. CAN hacia la UCH: A3/A4 (no tocar).
- Precalentamiento: C-F2 / D3. Alimentaciones: A-D1, A-G1, C-G2/H2, masas G1/H1.
- En la tabla NO aparece ninguna salida de consumo ni de velocidad hacia el cuadro (ver §5).

### Otras fuentes de pines (con cautela)
- lemondedudiagauto (Clio II 2004 1.5 dCi que no arranca): D1 en el conector negro = +APC por el fusible F5 de 15 A (777); A3/A4 hacia los pines 19/20 de la UCH (645); relé de inyección J mandado a masa por la ECU (F1). Parte de esto viene de un resumen, no del texto literal.
- cliosport (MWright): B8-B11 y G5 son pines de la **R107** (otra centralita, de petróleo RS), **no de la DDCR**.
- Documento **Delphi DDNX243 (10/2005)**, subido al proyecto como PDF («ecu-pinout»): tabla «DCU inputs/outputs» con conectores CH (negro), CMI (marrón) y CME (gris). Es otra aplicación Delphi DCR (incluye entrada «Speedo», «Vehicle speed», «Immob. transmission/reception», «Clutch switch» en CH-E3 y «Line K» en CH-B4). **NO coincide con el pineado Renault**: no usarla para el Clio, solo como referencia de qué funciones puede tener la familia DCR.

---------------------------------------------------------------------
## 3. REGULADOR / LIMITADOR SIN PREINSTALACIÓN
Fuente principal: brico de **crossmax**, ClubClio España, hilo «Instalacion Regulador/Limitador Velocidad sin preinstalacion» (https://www.clubclio.com/viewtopic.php?t=73283, 240 mensajes en 16 páginas, revisado entero). Su coche: Clio II fase 2 1.5 dCi 80 cv Billabong.
Otras fuentes: brico con preinstalación de Shiryu (https://www.clubclio.com/viewtopic.php?p=1024939), montaje argentino de yara/Fer en un Clio dCi 65 de 2006 (https://www.clubclio.com/viewtopic.php?f=2&t=57965&start=75), cliosport.net y planeterenault.

### Requisitos
- Acelerador electrónico: solo fase 2 o posterior. **Fase 1: no.**
- dCi K9K: confirmado en varios montajes. Gasolina: pines distintos según la ECU. **1.2 8v (Siemens Sirius 32): no**, los pines están ocupados. En un D4F salió «SET», pero al pulsar los botones cortaba gas y encendía el testigo de avería.
- ¿Preinstalación? Detrás de la tapa de la ruleta de altura de faros: si solo están el conector de faros y el de iluminación del cuadro, no hay. Si aparece un **conector blanco** suelto (5 vías), sí: amarillo = común, verde = regulador, gris = limitador. Ojo: el conector de al lado da luz al cuadro y, si se desconecta, el cuadro se apaga. Puede haber preinstalación parcial (p. ej. el cable del embrague hasta el conector de 10 vías del pedal del acelerador).
- El contactor de freno viene de serie y ya va a la ECU.

### Piezas y referencias
| Pieza | Referencia | Notas |
|---|---|---|
| Terminales (pines) para el conector de la ECU ×5 | 7703497275 | o sacarlos de un conector de desguace |
| Interruptor REG/LIM | 8200107841 | ~22 €; vale el de Mégane; en cliosport citan 8200060039 |
| Tapa de 2 huecos (faros + interruptor) | 8200084862 | la de 3 huecos (con ESP) es la 8200084863 |
| Contactor de embrague | 8200168240 | en foros ingleses 7700431512; dicen que debe ser verde, pero a crossmax le funcionó otro |
| Soporte del contactor de embrague | 7700430730 | |
| Botones de volante | 8200060038 | ~58 €; los de Mégane no valen |
| Contactor giratorio con pistas para mandos | 7701051757 | ~120 €; uno sin mandos tiene 4 vías y el preparado 6 |
| Mazo del pedal (opcional) | 8200570012 / 8200234517 | conector morado del embrague |
| Cable | ~2,5 m, 5 hilos, ~0,35-0,5 mm² | no usar UTP de red en la parte de +12 V |

### Montaje
1. Desconectar la batería. Conector derecho de la ECU: girar la pieza gris un cuarto de vuelta, sacar el **peine verde** de bloqueo y el capuchón (2 pestañas). Insertar los 5 pines en **A2, C3, D2, D3 y C4** hasta oír el clic, con alicates de punta fina. El peine verde tiene que estar fuera al insertar.
2. Pasar los cables al habitáculo por el **pasamuros del cable del capó**, dentro de un termorretráctil y con una guía. Identificarlos con continuidad del polímetro (truco del montaje argentino).
3. Interruptor (conector A1 A2 A3 / B1 B2 B3):
   - A1 → masa (cable GRIS del conector de altura de faros)
   - B2 → + iluminación (cable AZUL del mismo conector; en el esquema, fusible F26 de 10 A)
   - A2 → +12 V: pata superior del **fusible F2 de 15 A «STOP»** (2ª fila, el primero de la izquierda; cable amarillo con raya gris)
   - B1 → ECU **C3**
   - A3 → ECU **A2**
4. Botones: la ECU lee una **resistencia entre D2 y D3**:
   - «0» (pausa) ≈ 0 Ω
   - «−» ≈ 100 Ω
   - «+» ≈ 274-300 Ω
   - «R» (reanudar) ≈ 900-910 Ω
   (valores del manual del Laguna II y de cliosport; el circuito de crossmax da exactamente esos valores)
   - **Opción A, satélite de la radio + red de resistencias** (crossmax): pines del satélite A1, B3, A3, B2, B1. Rama D2: A1 –200 Ω– nodo con B3 –100 Ω– nodo con A3 → D2. Rama D3: B2 –680+120+100 Ω– nodo con B1 → D3. Funciones: botón inferior = 0; botones superiores = R; Vol+ = +2 km/h; Vol− = −2 km/h (también activan con la velocidad actual).
   - **Opción B, botones originales**: contactor giratorio 7701051757; D2/D3 a las dos vías extra del conector del contactor; los botones ya llevan sus resistencias. Desmontar el airbag (2 grapas), Torx del volante, carcasas (3 Torx), mandos (2 Torx cada uno); la tapa del airbag necesita hueco para los botones.
   - **Opción C, botonera propia**: 4 pulsadores NA, cada uno con su resistencia en serie, todos en paralelo entre D2 y D3.
5. Embrague: un hilo del contactor a **C4** y el otro a masa (el orden da igual). Si no hace contacto, poner un suplemento de plástico o un plomo pequeño en el pedal. Sin contactor y con **C4 al aire**: solo funciona el limitador y hay tirones. Con **C4 a masa fija**: funciona también el regulador, pero al embragar el motor se embala hasta que la ECU corta.

### Pruebas y uso
- Test del cuadro: mantener pulsado el botón del ordenador de a bordo al dar contacto; el testigo REG/LIM debe encenderse.
- Interruptor en REG o LIM: testigo verde (regulador) o naranja (limitador) y «SET ---» en la última pantalla del ordenador de a bordo. Una vez detectado, «SET» puede quedarse siempre.
- Solo funciona circulando: a partir de ~30 km/h y con 2ª marcha o más.
- Regulador: +/− memoriza la velocidad actual y ajusta de 2 en 2 km/h; «0» pausa; «R» recupera. Freno y embrague desconectan.
- Limitador: para pasar del límite, pisar a fondo atravesando el punto duro del acelerador.
- Prueba sin interruptor: puentear el +12 V STOP con A2 o C3.

### Averías del hilo
- SET pero sin testigo → cuadro sin testigo: hay que montar un cuadro de un Clio con ordenador de a bordo.
- Testigo y SET pero los botones no hacen nada → resistencias mal o cables cruzados con los del interruptor.
- El interruptor no queda enclavado → interruptor roto o de otra referencia.
- Limitador OK pero el regulador no fija velocidad → contactor de embrague o punto duro del acelerador.
- Nada de nada → fusible o +12 V, pines mal encajados (¿peine verde?), ECU incompatible o función desactivada.

### ¿Hay que activarla por diagnóstico?
El foro no se pone de acuerdo («más veces no que sí»). Shiryu y crossmax no activaron nada; el montaje argentino dice que sí hace falta. **Si sale «SET ---», ya está activa.** No se encontró ninguna fuente fiable con el parámetro exacto (CLIP, DDT4All).

PDF de 24 páginas con todo lo anterior, fotos del foro y esquemas: «Regulador_Limitador_Clio_II_sin_preinstalacion.pdf» (está en el chat anterior; hay que subirlo a mano).

---------------------------------------------------------------------
## 4. ESQUEMA RENAULT (componentes)
120 = ECU de inyección · 1081 = interruptor marcha/paro del limitador/regulador · 627 = mando del regulador (botones) · 1016 = caja de fusibles del habitáculo (F2 15 A STOP, F26 10 A) · MAM = masa · 645 = UCH · R67 y R107 = conectores intermedios.

---------------------------------------------------------------------
## 5. ORDENADOR DE A BORDO
- Por lo encontrado, el cuadro básico no se puede activar: hay que montar un **cuadro con ordenador de a bordo de un Clio II fase 2** (mejor de dCi; los de fase 1 tienen otros conectores) + el **mando del limpiaparabrisas con el botón** en la punta.
- Se ve en la misma pantalla del cuadro: kilómetros totales, parcial, combustible gastado, consumo medio e instantáneo, autonomía, distancia y velocidad media. El «SET» del regulador también sale ahí.
- La ECU no tiene salida de consumo por cable (no aparece en el pinout). Probablemente va por CAN a la UCH y de ahí al cuadro (sin confirmar). No basta con tirar un cable desde la ECU.
- Tras el cambio hay que ajustar los kilómetros y puede que configurar el cuadro con diagnóstico (Renolink podría servir; no comprobado en Clio II).
- Fuentes sin leer (bloqueadas a la lectura automática; se pueden leer con el navegador): ClubClio «Lo conseguí: ordenador de a bordo» (https://www.clubclio.com/viewtopic.php?t=20477), ClubClio t=13538, forum-clio «[2.2] Ajouter l'Ordinateur De Bord [TUTO]» (https://www.forum-clio.com/index.php?topic=425.0), forum-clio topic 999 (montaje de un cuadro con ordenador de a bordo), forum-auto caradisiac 489053 y 128060.
- Ojo: en los foros franceses «ODB» = ordinateur de bord, no OBD.
- Alternativa sin cambiar el cuadro: Torque en la radio Android con el adaptador OBD, o una pantalla propia con ESP32 (§7).

---------------------------------------------------------------------
## 6. INTERFACES Y SOFTWARE
- **Su cable** (rojo transparente, cable naranja, etiqueta «OBDLink SX»): es un clon de ELM327 USB con chip FTDI, tipo Renolink, no un OBDLink SX original. Necesita soportar línea K (ISO 9141 / KWP2000) y, si tiene interruptor de modo, estar en la posición correcta.
- **Can Clip** y **Delphi DS150 / Autocom** NO funcionan con un ELM327 ni con un Arduino o ESP32: usan su propia interfaz con protocolo cerrado, y el programa comprueba el número de serie y el firmware. Los clones chinos que funcionan son copias de la placa original (Actia / DS150E, ~30-60 €). No se ayuda a saltarse esa comprobación.
- **Programas que sí funcionan con ELM327 USB:**
  - **Renolink** (de pago): el primero que probar con la DDCR y la UCH por línea K.
  - **pyren** (gratis): base de datos de Renault, parecido a Can Clip; muy bueno por CAN, por línea K en ECUs antiguas sin confirmar.
  - **DDT4All** (gratis): configuración avanzada (DDT2000); admite ELM327, Vlinker, OBDLink SX/EX. Más riesgo.
  - **ECUTwea**: solo coches con CAN (no sirve para el Clio II).
  - **Torque / Car Scanner / OBD Auto Doctor**: solo OBD genérico.
- Antes de escribir configuración: copia de seguridad y cargador de batería conectado (un corte puede dejar la ECU o el cuadro inservibles).
- Documento del proyecto «Renault CAN/K-line ECU Tool V1.01» (Immo-Tools.lt, 2011): herramienta OBD para leer/escribir EEPROM y FLASH y borrar el código de antiarranque. Soporta Bosch EDC15C3, Siemens SID301, SIRIUS32, SIRIUS34, EMS3132, Sagem SAFIR/SAFIR2, Magneti Marelli IAW 6R.30 y Valeo BII del Espace III. **No soporta la Delphi DDCR del K9K.** Útil como referencia de lo que se puede hacer por línea K en ECUs Renault de la época.

---------------------------------------------------------------------
## 7. PROYECTO ESP32 / ARDUINO POR LÍNEA K (deep research verificado)
Conclusión: viable y barato. Lo difícil es el firmware, no el hardware.

- **Hardware** (~5-15 €): ESP32 DevKit + transceptor de línea K **L9637D o MC33290** (también Si9241, SN65HVDA195, un LM393 o transistores) + regulador de 12 V a 5/3,3 V + diodo + fusible + conector OBD macho. Pines OBD: **7 = línea K, 16 = +12 V, 4/5 = masa** (el 15 = línea L, en algunas ECU). Para el Clio no hace falta CAN.
- **Firmware ya hecho:**
  - **muki01/OBD2_K-line_Reader** (https://github.com/muki01/OBD2_K-line_Reader): ISO 9141-2 con init a 5 baudios, KWP2000 slow init y fast init, con autodetección; probado en Arduino y ESP32 (el autor dice que también va en ESP8266, STM32 y Pico).
  - **iwanders/OBD9141** (https://github.com/iwanders/OBD9141): con ejemplo para ESP32 (UART2); en el Uno necesita AltSoftSerial. Probado con MC33290, SN65HVDA100 y SN65HVDA195.
- **Arduino Uno vs ESP32:** el Uno no tiene UART libre, tiene poca RAM y no lleva BT/WiFi → dificultad media-alta. El ESP32 tiene varias UART, CAN nativo (TWAI) y BT/WiFi → dificultad media.
- Emuladores ELM327 con ESP32 que ya existen (**EQM_OBDWEB, WiCAN**) son **solo CAN**: no sirven para el Clio tal cual.
- **Emular el ELM327** por línea K para que lo reconozcan pyren, DDT4All o Torque (comandos ATZ, ATE, ATL, ATS, ATSH, ATH, ATSP, ATKW, flow control, timings P1-P4, eco de la línea): difícil, semanas de trabajo. No hay ningún proyecto probado en un Renault por línea K.
- **Chips de los clones ELM327:** los buenos (v1.5, placas V01_M_V2.3 y V1.5_S_V2.0) llevan **PIC18F25K80** + Bluetooth YC1021/BC417/BK3231 + EEPROM 24C32/24C64. El PIC se puede reflashear con el firmware abierto **CanAdapterElm (ediabaslib / Deep OBD)** con un PICkit 3/4, que añade línea K completa (KWP2000, KW1281, TP2.0); la primera carga tiene que ser el .unified.hex. Los malos (los «v2.1») llevan un Beken BK3231 + MCP2515/TJA1050 o un chip sin marcar con cristal de 24 MHz, tienen firmware con fallos y rechazan comandos AT. Cables KKL: chip USB-serie FTDI o CH340 + transceptor o transistores.
- **Sin comprobar:** si la DDCR responde tal cual a estos firmwares (Renault usa direcciones y servicios propios dentro de KWP2000, no solo OBD genérico), si hay que usar init a 5 baudios o fast init, y qué timings tolera.
- Plan recomendado:
  1. Diagnóstico ya: el cable actual con Renolink / pyren, o un ELM327 USB con PIC18F25K80 (~10-15 €).
  2. Proyecto: ESP32 + L9637D + firmware muki01 → comprobar que la DDCR responde → leer datos para una pantalla propia o el regulador con ESP32.
  3. Emular el ELM327 solo si de verdad hace falta.

---------------------------------------------------------------------
## 8. OTROS DOCUMENTOS DEL PROYECTO
- «ecu-pinout» (PDF): Delphi DDNX243 10/2005, tabla «DCU inputs/outputs» CH/CMI/CME. **Es otra aplicación, no la DDCR del Clio** (ver §2).
- «mCs6rKS.jpg»: esquema eléctrico del aire acondicionado de un vehículo con K9K700 / F9Q782 (tipo Kangoo/Kubistar): presostato del A/C B161, módulo de control del A/C A63, módulo del ventilador A176, ECU A35.
- «Renault CAN/K-line ECU Tool V1.01» (PDF): ver §6.
- «canbus_intro_llm»: documentación del CANsub (CSS Electronics), un interfaz CAN; no es directamente aplicable a la línea K del Clio.

---------------------------------------------------------------------
## 9. FUENTES
- ClubClio t=73283 (crossmax), p=1024939 (Shiryu), t=57965&start=75 (montaje argentino), t=20477 y t=13538 (ordenador de a bordo)
- infoscenic.com – Calculateur d'injection diesel : Branchement (pinout K9K DDCR)
- cliosport.net – «Cruise control on a RS 172 or a dCi DIY» (páginas 3-4), «Cruise control resistors», «dCi cruise control retrofit»
- renaultbook.ru – Laguna II, regulador/limitador (escalera de resistencias, condiciones de funcionamiento)
- planeterenault.com – «[Clio II] ODB et régulateur limiteur de vitesse» (t2783)
- lemondedudiagauto.com t26731 (Clio II 1.5 dCi no arranca: D1, A3/A4, UCH)
- autoastuce.com y calculateurs-moteurs.com (referencias de la DDCR)
- autoscoop.fr – Tableau de bord Clio II
- Manuales de usuario oficiales X65: Renault Uruguay (X65_NU_1016-1_ESP_82754.pdf), Clio Mío Renault Argentina
- Scribd EC-K9K (248 páginas, manual del motor K9K; probablemente tiene el pinout oficial; requiere cuenta)
- GitHub: muki01/OBD2_K-line_Reader, iwanders/OBD9141, uholeschak/ediabaslib, EQMOD/EQM_OBDWEB, meatpiHQ/wican-fw, emtee40/pyren-OBD2, cedricp/ddt4all, Ircama/ELM327-emulator
- transparentcar.blogspot.com y cnx-software.com (desmontajes de ELM327 falsos)

---------------------------------------------------------------------
## 10. PENDIENTE / SIGUIENTES PASOS
1. Leer con el navegador (Claude in Chrome con un solo navegador conectado) los tutoriales del ordenador de a bordo (ClubClio t=20477, forum-clio topic 425 y 999) y sacar referencias del cuadro, el mando y el cableado.
2. Conseguir el EC-K9K de Scribd para confirmar el pinout oficial del Clio y si C4 es el embrague.
3. Probar Renolink con el cable actual: ¿ve la DDCR y la UCH? ¿Aparece alguna configuración de regulador o del cuadro?
4. Proyecto ESP32: esquema ESP32 + L9637D y código de prueba para conectar con la DDCR por línea K.
5. Decidir entre regulador de fábrica (cablear la ECU) o regulador propio con ESP32.
