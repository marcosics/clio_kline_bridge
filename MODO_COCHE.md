# Modo coche: registro continuo + IA

Qué hace: el portátil va en el coche conectado al puente ESP (o al cable ELM), lee la línea K sin parar
(conduciendo o parado), lo guarda todo, vigila anomalías y averías, y Claude revisa, aprende y rediseña el panel solo.
**Solo lectura**: nada escribe en las centralitas. Los cambios de configuración se hacen a mano con DDT4ALL/Renolink.

## Esquema

```
 [UCE 0x7A + ABS 28 + UCH 26…] ─línea K─ [ESP-01 + LM339]
                                            │  Wi-Fi: se une al hotspot del móvil (y crea su red CLIO-KLINE)
 [Móvil: zona wifi con datos] ──────────────┤
                                            │
 [Portátil] ─ clio_web.py (único tester): registra, detecta, sirve el Panel
             └ Claude (clio_mcp.py): lee eventos y registros, aprende, rediseña el Panel, apunta en su memoria
 [Móvil / radio Android] ── navegador → http://IP-del-portátil:8080 (ver el Panel mientras conduces)
```

¿Por qué el hotspot del móvil? Si el portátil se conecta a la red del ESP, se queda sin internet y Claude no
funciona. Uniéndolos todos a la zona wifi del teléfono, el portátil tiene internet y ve el puente a la vez.
Con el cable ELM por USB no hace falta: el wifi del portátil queda libre para el móvil.

## Puesta en marcha (una vez)

1. Firmware con tu zona wifi: en `firmware/platformio.ini`, sección `[movil]`, pon el nombre y la clave de la zona
   wifi del teléfono y quita el `;` de la línea `flags`. Graba: `python -m platformio run -d firmware -e esp01 -t upload`.
2. En el portátil: `pip install pyserial mcp` y Claude Code instalado (`claude` en la terminal).
3. Prueba sin coche: `python tools/clio_web.py --auto sim --drive` → http://localhost:8080 (pestaña Panel).

## Cada viaje

1. Activa la zona wifi del móvil y conecta el portátil a ella.
2. Doble clic en `arrancar_coche.bat` (o a mano):
   ```
   python tools/clio_web.py --lan --auto bridge:auto --drive --otras "28:A0;26:80" --ia-auto 30
   ```
   - `--auto bridge:auto`: busca el puente (clio-kline.local, aviso UDP o 192.168.4.1) y reconecta solo.
     Con el cable ELM: `--auto elm:COM5`.
   - `--drive`: registro continuo de la inyección (A0, A1, A2) en `logs/drive_*.jsonl`.
   - `--otras`: cada 60 s visita otras centralitas (ABS, UCH…) y vuelve. Quítalo si no responden.
   - `--ia-auto 30`: Claude revisa cada 30 min y cuando aparece una avería o anomalía (con tope diario de veces y $).
   - `--lan`: para ver el Panel desde el móvil o la radio (http://IP-del-portátil:8080).
3. Conduce. El Panel se actualiza solo; la pestaña Modo coche enseña eventos, IA automática y el chat con Claude.

## Qué hace la IA sola

- Lee su memoria (`tools/ia_memoria.md`), los eventos y el resumen del registro.
- Autodescubrimiento: canales que cambian, contadores, bits que conmutan y parejas de canales que se mueven juntos
  (p. ej. un byte que sigue al régimen en cada marcha = velocidad candidata). Lo cruza con la base DDT4ALL si está.
- Guarda las variables con evidencia (`decode_set`) y las hipótesis con «?».
- Rediseña el Panel (`ui_page`): lo que avisa de fallos arriba, lo nuevo, y páginas de configuración que muestran
  cada parámetro de la base DDT (si es de escritura, solo dice cómo cambiarlo con DDT4ALL).
- Puede escribir y ejecutar scripts de análisis en `analisis/` (leen `logs/`; no tocan el puerto).
- Si ve algo urgente escribe «ALERTA: …», que sale como evento en el Panel.

## Pedirle cosas

En Modo coche → chat: «hazme una página con consumo y autonomía», «¿por qué sube la presión de rail al frenar?»,
«compara el viaje de hoy con el de ayer». Sigue la misma conversación y recuerda lo hablado.

## Coste y seguridad

- Cada revisión de la IA cuesta céntimos (según lo que lea). Topes en Modo coche: veces/día y $/día.
- No uses `ask_user` conduciendo: la IA no te pide acciones mientras registra.
- Toda petición pasa la lista blanca (10C0, 3E, 21, 17, 18, 1A) en la web y en el firmware. La IA no puede escribir.
