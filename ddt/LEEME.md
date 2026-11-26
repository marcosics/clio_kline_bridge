# Base DDT4ALL

Pon aquí `ecu.zip`: es la base de DDT4ALL, que contiene `db.json` y un JSON por centralita. También valen los `*.json` sueltos.

La base no es pública. Se genera desde tu DDT2000, con `ddt4all -z` desde la carpeta que contiene `ecus/*.xml`.
Después reinicia `tools/clio_web.py`.

Una vez cargada, en la web:
- Configuración → Leer 2180 → «Cargar» el archivo que mejor encaje.
- Endian «Little» para la DDCR (ver CLAUDE.md, sección 5).
