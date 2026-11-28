#!/usr/bin/env python3
"""
clio_mcp.py - Servidor MCP para Claude. NO abre el puerto: habla con tools/clio_web.py (http://127.0.0.1:8080),
que es el unico tester en la linea K. Asi la web y Claude ven y usan la misma conexion a la vez.
Solo lectura en el coche (lista blanca de clio_web.py). Lo unico que escribe son archivos locales del proyecto.

  python tools/clio_web.py                 (primero, en otra terminal)
  claude mcp add clio-kline -- python tools/clio_mcp.py
"""
import json, os, urllib.error, urllib.request
from mcp.server.mcpserver import MCPServer

WEB = os.environ.get("CLIO_WEB", "http://127.0.0.1:8080")
mcp = MCPServer("clio-kline", instructions=(
    "Diagnostico del Renault Clio II 1.5 dCi (UCE Delphi DDCR 0x7A) por linea K, a traves de la web local clio_web.py. "
    "Flujo: status -> connect -> ident -> read_dtc / live / scan_lids. Para descubrir que significa cada byte: "
    "learn_start, pedir al usuario la accion, learn_mark, learn_stop, learn_analyze; luego guardar lo aprendido con "
    "decode_set. Modo coche: drive_status/drive_summary/events/analyze_drive para el registro continuo; ui_get/ui_page "
    "para disenar el panel de la web; memory_get/memory_add para tu memoria entre sesiones. "
    "Nunca se puede escribir en la UCE desde aqui: configuraciones con DDT4ALL a mano."))


def call(path, body=None, timeout=600):
    req = urllib.request.Request(WEB + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return e.read().decode()
    except urllib.error.URLError as e:
        return json.dumps({"error": f"La web no responde en {WEB} ({e.reason}). Arranca: python tools/clio_web.py"})


@mcp.tool()
def status() -> str:
    """Estado: conectado o no, backend, UCE seleccionada, grabacion de aprendizaje activa, base DDT cargada."""
    return call("/api/status")


@mcp.tool()
def connect(backend: str, address: str = "", baud: int = 0, ecu: str = "7A", init: str = "fast") -> str:
    """Conecta. backend: sim | elm (address COM5) | bridge (COM6 o tcp:192.168.4.1:23).
    ecu: 7A inyeccion, 28 ABS, 26 UCH, 2C airbag, 51 cuadro. init: fast (ISO14230 fast init) | slow (5 baudios, solo ELM)."""
    return call("/api/connect", {"backend": backend, "address": address, "baud": baud, "ecu": ecu, "init": init})


@mcp.tool()
def select_ecu(ecu: str, init: str = "fast") -> str:
    """Cambia de centralita sin desconectar el adaptador (nuevo init + 10C0)."""
    return call("/api/select_ecu", {"ecu": ecu, "init": init})


@mcp.tool()
def ecu_scan(ecus: list[str] | None = None, init: str = "fast") -> str:
    """Prueba que centralitas responden (init + 2180 en cada direccion) y vuelve a la actual."""
    return call("/api/ecu_scan", {"ecus": ecus or [], "init": init})


@mcp.tool()
def ident() -> str:
    """Identificacion 2180 de la UCE actual (hex, ASCII y, si hay base DDT, campos decodificados)."""
    return call("/api/ident")


@mcp.tool()
def read_dtc() -> str:
    """Averias (servicios 17 y 18). Borrar (14) no esta permitido."""
    return call("/api/dtc")


@mcp.tool()
def live(lids: str = "A0,A1,A2") -> str:
    """Lee una vez los LIDs (21xx) y devuelve bytes y valores decodificados (tabla local + base DDT)."""
    return call("/api/live?lids=" + lids)


@mcp.tool()
def scan_lids(start: int = 1, end: int = 255) -> str:
    """Barre 21xx y devuelve los LIDs que responden. Guarda logs/scan_*.json."""
    return call("/api/scan", {"start": start, "end": end})


@mcp.tool()
def send(request_hex: str) -> str:
    """Peticion KWP2000 cruda (solo 10C0, 3E, 21, 17, 18, 1A) o comando del adaptador: AT... (ELM) o del puente ESP:
    STATUS, STATS, TEST LINE, TEST ECHO, LOGDUMP, TIMING, CONFIG, SET, NET, SCAN, SNIFF ON, LOG 2... (ver firmware/LEEME.md)."""
    return call("/api/console", {"line": request_hex})


@mcp.tool()
def serial_log(n: int = 100) -> str:
    """Ultimas lineas del log serie del puente ESP (TX/RX/ECHO/RAW/DBG/ERR)."""
    return call(f"/api/serial_log?n={n}")


@mcp.tool()
def learn_start(name: str, lids: str = "A0,A1,A2", period_ms: int = 200) -> str:
    """Empieza a grabar los LIDs en logs/rec_<name>_*.jsonl. Despues usa learn_mark al cambiar de estado."""
    return call("/api/learn/start", {"name": name, "lids": lids, "period_ms": period_ms})


@mcp.tool()
def learn_mark(label: str) -> str:
    """Marca un cambio de estado en la grabacion (p. ej. 'reposo', 'freno pisado', 'embrague', 'motor 2000rpm')."""
    return call("/api/learn/mark", {"label": label})


@mcp.tool()
def learn_stop() -> str:
    """Para la grabacion y devuelve el archivo."""
    return call("/api/learn/stop", {})


@mcp.tool()
def learn_analyze(file: str = "") -> str:
    """Analiza una grabacion (la ultima si no se indica): por cada marca, que bytes/bits cambian respecto a la
    primera marca, y rango de cada byte y de cada u16 little endian."""
    return call("/api/learn/analyze", {"file": file})


@mcp.tool()
def recordings() -> str:
    """Lista las grabaciones de aprendizaje y escaneos guardados en logs/."""
    return call("/api/recordings")


@mcp.tool()
def decode_get() -> str:
    """Tabla local de decodificacion (tools/ddcr_decode.json): lo aprendido hasta ahora."""
    return call("/api/decode")


@mcp.tool()
def decode_set(lid: str, name: str, byte: int, length: int = 1, scale: float = 1, offset: float = 0,
               unit: str = "", le: bool = True, bit: int = -1, note: str = "") -> str:
    """Guarda/actualiza una variable aprendida en tools/ddcr_decode.json (archivo local, no la UCE).
    byte = indice tras '61 xx'. bit >= 0 para un solo bit. Se ve al momento en el tablero de la web."""
    return call("/api/decode", {"lid": lid, "name": name, "byte": byte, "len": length, "scale": scale,
                                "offset": offset, "unit": unit, "le": le, "bit": bit, "note": note})


@mcp.tool()
def auto_explore(ecus: list[str] | None = None, full_scan: bool = True, sample_s: float = 5, init: str = "fast") -> str:
    """Exploracion automatica en segundo plano: por cada UCE init, 2180, averias, escaneo de LIDs (todos si full_scan)
    y muestreo con clasificacion de cada byte (constante/contador/variable). Resultado en logs/explore_*.json.
    Consulta el avance con job_status."""
    return call("/api/auto/explore", {"ecus": ecus or [], "full_scan": full_scan, "sample_s": sample_s, "init": init})


@mcp.tool()
def job_status() -> str:
    """Estado del trabajo en segundo plano (exploracion): progreso y archivo de resultado."""
    return call("/api/job")


@mcp.tool()
def ask_user(text: str, timeout_s: int = 300) -> str:
    """Pregunta o pide una accion al usuario en la web (p. ej. 'Pisa el freno y pulsa Hecho') y espera su respuesta."""
    return call("/api/ai/ask", {"text": text, "timeout": timeout_s}, timeout=timeout_s + 30)


@mcp.tool()
def db_status() -> str:
    """Base DDT4ALL: si esta cargada, archivo de la UCE elegido y numero de peticiones/datos."""
    return call("/api/db/status")


@mcp.tool()
def db_search(text: str) -> str:
    """Busca en la base DDT4ALL de la UCE actual peticiones y datos por nombre (p. ej. 'vitesse', 'frein', 'regul')."""
    return call("/api/db/search", {"text": text})


@mcp.tool()
def db_read(request_name: str) -> str:
    """Envia una peticion de LECTURA definida en la base DDT4ALL y la decodifica con sus definiciones."""
    return call("/api/db/read", {"name": request_name})


# ---------------------------------------------------------------- modo coche
@mcp.tool()
def drive_start(main_ecu: str = "7A", main_lids: str = "A0,A1,A2", period_ms: int = 250,
                others: str = "", other_every_s: int = 60, dtc_every_s: int = 60) -> str:
    """Arranca el registro continuo (logs/drive_*.jsonl). others: 'ECU:LID,LID;ECU:LID' (p. ej. '28:A0;26:80'),
    se visitan cada other_every_s segundos. Reconecta solo si se cae la linea."""
    oth = [{"ecu": o.split(":")[0].upper(), "lids": o.split(":")[1].upper().split(",") if ":" in o else [], "dtc": True}
           for o in others.split(";") if o.strip()]
    return call("/api/drive/start", {"plan": {"main_ecu": main_ecu.upper(), "main_lids": main_lids.upper().split(","),
                                              "period_ms": period_ms, "others": oth, "other_every_s": other_every_s,
                                              "dtc_every_s": dtc_every_s}})


@mcp.tool()
def drive_stop() -> str:
    """Para el registro continuo."""
    return call("/api/drive/stop", {})


@mcp.tool()
def drive_status() -> str:
    """Estado del registro continuo: en marcha, muestras, archivo, plan, eventos y canales vigilados."""
    return call("/api/drive/status")


@mcp.tool()
def drive_summary(top: int = 40) -> str:
    """Canales que varian (byte bN, u16 little endian uN y variables v:nombre) con media, desviacion, min, max y
    numero de cambios, mas la ultima respuesta de cada UCE:LID."""
    return call(f"/api/drive/summary?top={top}")


@mcp.tool()
def drive_series(keys: str, n: int = 300) -> str:
    """Serie temporal reciente [t, valor] de una o varias claves separadas por comas:
    '7A:A1:rpm' (variable), '7A:A1:b3' (byte), '7A:A1:u3' (u16 LE), '7A:A1:b5.2' (bit)."""
    return call(f"/api/drive/series?key={keys}&n={n}")


@mcp.tool()
def events(minutes: float = 60, kinds: str = "") -> str:
    """Eventos del modo coche: averia, anomalia, descubrimiento (byte dormido que despierta), comunicacion, conexion,
    ia (alertas). kinds: filtro separado por comas."""
    return call(f"/api/events?minutes={minutes}&kinds={kinds}")


@mcp.tool()
def drives() -> str:
    """Lista los registros de conduccion guardados (logs/drive_*.jsonl)."""
    return call("/api/drives")


@mcp.tool()
def analyze_drive(file: str = "") -> str:
    """Autodescubrimiento sobre un registro (el actual si no se indica): canales que varian, contadores, bits que
    conmutan (con instantes) y parejas de canales muy correlacionadas (|r|>0.85)."""
    return call("/api/discover", {"file": file})


@mcp.tool()
def ui_get() -> str:
    """Panel de la web (tools/ui_layout.json): paginas y widgets. Lee '_ayuda' para los tipos y claves."""
    return call("/api/ui")


@mcp.tool()
def ui_page(page_json: str) -> str:
    """Crea o sustituye una pagina del panel. JSON: {"id","title","widgets":[...]}. Tipos de widget: value, gauge
    (min,max), chart (key o keys), bits (key de byte), table (keys), text (text), dtc, events, request (name de la base
    DDT: lectura = boton leer; escritura = solo instrucciones para DDT4ALL), raw (key 'ECU:LID').
    Campos comunes: title, key, unit, scale, offset, warn_hi, warn_lo, note."""
    try:
        page = json.loads(page_json)
    except ValueError as e:
        return json.dumps({"error": f"JSON invalido: {e}"})
    return call("/api/ui/page", {"page": page})


@mcp.tool()
def ui_set(ui_json: str) -> str:
    """Sustituye el panel completo ({"pages":[...]}). Se guarda una copia previa en ui_layout.prev.json."""
    try:
        ui = json.loads(ui_json)
    except ValueError as e:
        return json.dumps({"error": f"JSON invalido: {e}"})
    return call("/api/ui", {"ui": ui})


@mcp.tool()
def memory_get() -> str:
    """Tu memoria entre sesiones (tools/ia_memoria.md): lo que ya sabes del coche."""
    return call("/api/memory")


@mcp.tool()
def memory_add(text: str, section: str = "Notas") -> str:
    """Anade una entrada a tu memoria (breve: hallazgos, hipotesis, pendientes)."""
    return call("/api/memory", {"text": text, "section": section})


if __name__ == "__main__":
    mcp.run()
