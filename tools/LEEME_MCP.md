# clio-kline MCP

## Instalación (Windows, portátil)
```
pip install mcp pyserial
```

## Claude Desktop
Ajustes → Desarrollador → Editar config (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "clio-kline": {
      "command": "python",
      "args": ["C:\\ruta\\clio_mcp\\clio_mcp.py"],
      "env": { "CLIO_ALLOW_WRITE": "0" }
    }
  }
}
```
Reinicia Claude Desktop. Pon `"1"` en CLIO_ALLOW_WRITE solo cuando vayas a escribir configuración.

## Claude Code
```
claude mcp add clio-kline -e CLIO_ALLOW_WRITE=0 -- python C:\ruta\clio_mcp\clio_mcp.py
```

## Primera sesión
Contacto ON, motor parado, batería cargada (o cargador conectado). Pide a Claude:
"Conecta a COM5 con la UCE 7A, escanea los LIDs y lee averías".

## Archivos
- logs/: todo lo enviado y recibido, por sesión
- backups/: valor previo de cada LID antes de escribirlo
