"""python tools/test_clio_web.py  - pruebas sin hardware: seguridad, tramas, simulador, puente, base DDT y aprendizaje."""
import json, socket, tempfile, threading, time, zipfile
from pathlib import Path
import clio_web as w
import ddt_db

TMP = Path(tempfile.mkdtemp())
w.LOGS, w.LOG, w.DECODE = TMP, TMP / "web.jsonl", TMP / "decode.json"  # no tocar logs/ ni la tabla real
w.clio_drive.UI_FILE, w.clio_drive.MEMORY_FILE = TMP / "ui.json", TMP / "mem.md"

ECU = {"ecuname": "TEST_DDCR", "endian": "Big", "obd": {"protocol": "KWP2000", "funcaddr": "7A"},
       "requests": [{"name": "Lecture A1", "sentbytes": "21A1", "receivebyte_dataitems": {"Regime": {"firstbyte": 3}}},
                    {"name": "Ecriture CF582", "sentbytes": "3B01", "sendbyte_dataitems": {"CF582": {"firstbyte": 3}}}],
       "data": {"Regime": {"bitscount": 16, "scaled": True, "step": 1, "unit": "tr/min"}},
       "devices": [{"dtc": "0123", "name": "Captador de prueba"}]}


def test_safe():
    for ok in ("10C0", "3E", "21A1", "17FF00", "18FF00", "1A80"):
        assert w.safe(ok) == ok
    for bad in ("2E0101", "3B0101", "14FF00", "1085", "1081", "27 01", "3101", "11", "34", "36", "zz", "2"):
        try:
            w.safe(bad)
            raise AssertionError(f"{bad} no bloqueado")
        except ValueError:
            pass


def frame(dst, src, data):
    f = bytes([0x80 | len(data), dst, src]) + data
    return f + bytes([w.checksum(f)])


def test_frame():
    assert frame(0x7A, 0xF1, bytes.fromhex("21A1")).hex().upper() == "827AF121A1AF"  # ejemplo de CLAUDE.md
    assert w.frame_data(bytes.fromhex("827AF121A1AF")) == bytes.fromhex("21A1")


def test_ddt_decode():
    assert ddt_db.hex_value("61A11234", {"firstbyte": 3}, {"bitscount": 16}, "Big") == "1234"
    assert ddt_db.hex_value("61A11234", {"firstbyte": 3}, {"bitscount": 16}, "Little") == "3412"
    assert ddt_db.hex_value("61A140", {"firstbyte": 3, "bitoffset": 1}, {"bitscount": 1}, "Big") == "01"
    assert ddt_db.display_value("61A101", {"firstbyte": 3}, {"lists": {"1": "ON"}}, "Big") == "ON"
    assert ddt_db.display_value("61A1FF", {"firstbyte": 3}, {"scaled": True, "signed": True}, "Big") == "-1"
    assert ddt_db.display_value("61A10064", {"firstbyte": 3}, {"bitscount": 16, "scaled": True, "step": 0.5,
                                                               "offset": -10, "format": "0.0"}, "Big") == "40.0"
    assert ddt_db.parse_ident("6180" + "00" * 5 + "07" + "44454C50" + "00" * 4 + "ABCD" + "0102")["supplier"] == "DELP"


def make_db():
    folder = TMP / "ddt"
    folder.mkdir(exist_ok=True)
    with zipfile.ZipFile(folder / "ecu.zip", "w") as z:
        z.writestr("db.json", json.dumps({"TEST_DDCR.json": {"address": "7A", "ecuname": "TEST_DDCR", "autoidents": []}}))
        z.writestr("TEST_DDCR.json", json.dumps(ECU))
    w.state["db"] = ddt_db.Db(folder)


def test_sim_api():
    make_db()
    assert w.api("/api/connect", {}, {"backend": "sim", "ecu": "7A"})["ok"]
    d = w.api("/api/dtc", {}, {})
    assert d["17"]["dtc"] == [{"code": "0123", "status": "A0", "name": ""}]
    live = w.api("/api/live", {"lids": ["A1,33"]}, {})["lids"]
    assert len(live["A1"]["bytes"]) == 24 and "error" in live["33"]
    assert set(w.api("/api/scan", {}, {"start": 0x70, "end": 0xB0})["found"]) == {"80", "A0", "A1", "A2"}
    try:
        w.api("/api/console", {}, {"line": "14FF00"})
        raise AssertionError("14 no bloqueado")
    except ValueError:
        pass
    scan = w.api("/api/ecu_scan", {}, {})
    assert scan["7A"]["ok"] and scan["26"]["ok"] and scan["28"]["ok"] and not scan["2C"]["ok"] and w.state["ecu"] == "7A"


def test_db_api():
    assert w.api("/api/db/status", {}, {})["candidatos"][0]["file"] == "TEST_DDCR.json"
    assert w.api("/api/db/load", {}, {"file": "TEST_DDCR.json", "endian": "Little"})["requests"] == 2
    rq = {r["name"]: r for r in w.api("/api/db/requests", {}, {})["requests"]}
    assert rq["Lecture A1"]["lectura"] and not rq["Ecriture CF582"]["lectura"]
    v = w.api("/api/db/read", {}, {"name": "Lecture A1"})["values"][0]
    assert 800 <= int(v["value"]) <= 5000, v  # rpm del simulador, little endian
    try:
        w.api("/api/db/read", {}, {"name": "Ecriture CF582"})
        raise AssertionError("3B no bloqueado")
    except ValueError:
        pass
    dec = w.api("/api/live", {"lids": ["A1"]}, {})["lids"]["A1"]["decoded"]
    assert any(x["name"] == "Regime" and x["src"] == "ddt" for x in dec)
    assert w.api("/api/dtc", {}, {})["17"]["dtc"][0]["name"] == "Captador de prueba"
    assert w.api("/api/db/search", {}, {"text": "regi"})["requests"][0]["name"] == "Lecture A1"


def test_learn():
    w.api("/api/decode", {}, {"lid": "A1", "name": "rpm", "byte": 0, "len": 2, "le": True, "unit": "rpm"})
    w.api("/api/decode", {}, {"lid": "A1", "name": "flag", "byte": 0, "bit": 0})
    dec = {x["name"]: x for x in w.api("/api/live", {"lids": ["A1"]}, {})["lids"]["A1"]["decoded"]}
    assert 800 <= dec["rpm"]["value"] <= 5000 and dec["flag"]["value"] in (0, 1)
    w.api("/api/decode", {}, {"lid": "A1", "name": "flag", "byte": 0, "delete": True})
    assert [p["name"] for p in w.api("/api/decode", {}, {})["A1"]] == ["rpm"]
    w.api("/api/learn/start", {}, {"name": "t", "lids": "A1", "period_ms": 50, "label": "reposo"})
    time.sleep(0.4)
    w.api("/api/learn/mark", {}, {"label": "acelerador"})
    time.sleep(4.5)  # el rpm simulado cambia cada 0,1 s
    w.api("/api/learn/stop", {}, {})
    a = w.api("/api/learn/analyze", {}, {})
    assert a["marcas"] == ["reposo", "acelerador"], a
    assert 0 in a["rangos"]["A1"]["u16le_que_varian"]
    assert w.api("/api/recordings", {}, {})["files"]


def test_explore_and_ask():
    c = w.classify([b"\x01\x05\x10", b"\x01\x06\x30", b"\x01\x07\x20", b"\x01\x08\x20"])
    assert c["bytes_constantes"] == 1 and [x["tipo"] for x in c["bytes_que_cambian"]] == ["contador", "variable"]
    w.api("/api/connect", {}, {"backend": "sim", "ecu": "7A"})
    w.api("/api/auto/explore", {}, {"full_scan": False, "sample_s": 0.3})
    for _ in range(100):
        if not w.api("/api/job", {}, {})["running"]:
            break
        time.sleep(0.1)
    res = json.loads((TMP / w.api("/api/job", {}, {})["file"]).read_text(encoding="utf-8"))
    assert res["7A"]["responde"] and res["28"]["responde"] and not res["2C"]["responde"] and set(res["7A"]["lids"]) == {"80", "A0", "A1", "A2"}
    assert res["7A"]["analisis"]["A1"]["muestras"] > 0 and w.state["ecu"] == "7A"
    threading.Timer(0.3, lambda: w.api("/api/ai/answer", {}, {"answer": "hecho"})).start()
    assert w.api("/api/ai/ask", {}, {"text": "Pisa el freno", "timeout": 5})["answer"] == "hecho"
    assert w.api("/api/ai/ask", {}, {"text": "x", "timeout": 0.2})["answer"].startswith("sin respuesta")


def test_ai_reader():
    """El lector del stream-json de Claude, con un proceso falso."""
    evs = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "Leo la ident"},
                                                         {"type": "tool_use", "name": "mcp__clio-kline__ident", "input": {}}]}},
           {"type": "user", "message": {"content": [{"type": "tool_result", "content": "6180..."}]}},
           {"type": "result", "subtype": "success", "total_cost_usd": 0.12}]
    code = "import json,sys\nfor e in %r: print(json.dumps(e))" % evs
    p = w.subprocess.Popen([w.sys.executable, "-c", code], stdout=w.subprocess.PIPE, text=True, encoding="utf-8")
    w.state["ai"]["log"] = []
    w._ai_reader(p, TMP / "ai.log")
    log = w.state["ai"]["log"]
    assert log[0] == "💬 Leo la ident" and log[1].startswith("🔧 ident") and "6180" in log[2] and log[3].startswith("✅"), log


def test_drive_mode():
    """Modo coche con el simulador: registro continuo con otra UCE, eventos, panel, memoria y descubrimiento."""
    w.api("/api/connect", {}, {"backend": "sim", "ecu": "7A"})
    w.api("/api/decode", {}, {"lid": "A1", "name": "rpm", "byte": 0, "len": 2, "le": True, "unit": "rpm"})
    w.drive.plan["other_every_s"] = 1
    w.api("/api/drive/start", {}, {"plan": {"main_lids": ["A1", "A2"], "period_ms": 20, "dtc_every_s": 0.5,
                                            "others": [{"ecu": "28", "lids": ["A0"], "dtc": False}]}})
    time.sleep(3)
    st = w.api("/api/drive/status", {}, {})
    assert st["running"] and st["samples"] > 30, st
    lat = w.api("/api/drive/latest", {}, {})
    assert "7A:A1" in lat and "28:A0" in lat and w.state["ecu"] in ("7A", "28")
    vals = w.api("/api/drive/values", {"keys": ["7A:A1:rpm,7A:A2:b7.0,7A:A1:u0,28:A0:u0"]}, {})
    assert 800 <= vals["7A:A1:rpm"] <= 5000 and vals["7A:A2:b7.0"] in (0, 1) and vals["7A:A1:u0"] == vals["7A:A1:rpm"]
    ser = w.api("/api/drive/series", {"key": ["7A:A1:rpm"], "n": ["50"]}, {})["7A:A1:rpm"]
    assert len(ser) > 10 and ser[0][0] <= ser[-1][0]
    assert any(e["kind"] == "averia" for e in w.api("/api/events", {"minutes": ["5"]}, {})["events"])
    assert w.api("/api/drive/summary", {}, {})["canales_que_varian"]
    w.api("/api/drive/stop", {}, {})
    time.sleep(0.3)
    d = w.api("/api/discover", {}, {})
    assert "7A:A1" in d["lids"] and d["lids"]["7A:A1"]["canales"], d
    # el panel: validación, página nueva y copia previa
    ui = w.api("/api/ui", {}, {})
    assert ui["pages"]
    w.api("/api/ui/page", {}, {"page": {"id": "nueva", "title": "Nueva", "widgets": [{"type": "gauge", "key": "7A:A1:rpm"}]}})
    assert "nueva" in [p["id"] for p in w.api("/api/ui", {}, {})["pages"]]
    try:
        w.api("/api/ui/page", {}, {"page": {"id": "x", "widgets": [{"type": "escribir_uce"}]}})
        raise AssertionError("widget desconocido aceptado")
    except ValueError:
        pass
    w.api("/api/memory", {}, {"text": "rpm = A1 u16 byte 0", "section": "Variables"})
    assert "rpm = A1" in w.api("/api/memory", {}, {})["text"]
    assert w.api("/api/ai/auto", {}, {"enabled": False, "interval_min": 15})["interval_min"] == 15


def test_analyze_drive_correlation():
    fn = TMP / "drive_test.jsonl"
    with open(fn, "w") as f:
        for i in range(200):
            rpm = 900 + i * 10
            data = rpm.to_bytes(2, "little") + bytes([i % 256, (rpm // 40) & 0xFF, 7, 1 if i % 50 < 10 else 0])
            f.write(json.dumps({"t": i * 0.1, "ecu": "7A", "lid": "A1", "r": "61A1" + data.hex().upper(), "v": {}}) + "\n")
    d = w.clio_drive.analyze_drive(fn)
    ch = d["lids"]["7A:A1"]["canales"]
    assert ch["b2"]["tipo"] == "contador" and "b4" not in ch and "u0" in ch
    assert any({p["a"], p["b"]} >= {"7A:A1:u0", "7A:A1:b3"} for p in d["parejas_correlacionadas"]), d["parejas_correlacionadas"]
    assert any(b["canal"] == "7A:A1:b5.0" for b in d["bits"])


def test_discover_bridge():
    """El puente contesta 'CLIO <ip> <placa>' a 'CLIO?' por UDP; sin puente, se usa su AP 192.168.4.1."""
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u.bind(("127.0.0.1", 0))
    def esp():
        d, a = u.recvfrom(16)
        if d == b"CLIO?":
            u.sendto(b"CLIO 127.0.0.1 esp01", a)
    threading.Thread(target=esp, daemon=True).start()
    real = w.socket.socket
    class S(real):  # redirige la difusión al falso ESP local
        def sendto(self, data, addr):
            return super().sendto(data, u.getsockname())
    w.socket.socket = S
    try:
        assert w.discover_bridge(1) == "127.0.0.1"
    finally:
        w.socket.socket = real


def fake_bridge(srv):
    """Imita firmware/src/main.cpp en modo SIM por TCP."""
    c, _ = srv.accept()
    f = c.makefile("rwb")
    for line in f:
        l = line.decode().strip().upper()
        if l == "PING": out = ["OK 1 PONG"]
        elif l.startswith("INIT FAST"): out = ["TX 1 81 7A F1 81 6D", "RX 2 83 F1 7A C1 EF 8F 05", "OK 3 INIT"]
        elif l.startswith("SEND "):
            q = bytes.fromhex(l[5:])
            out = ["TX 1 " + frame(0x7A, 0xF1, q).hex(" ").upper(), "ECHO 2 ..",
                   "RX 3 " + frame(0xF1, 0x7A, w.sim_answer(q)).hex(" ").upper(), "OK 4 SEND"]
        else: out = ["OK 1 " + l]
        f.write(("\n".join(out) + "\n").encode())
        f.flush()


def test_bridge_tcp():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    threading.Thread(target=fake_bridge, args=(srv,), daemon=True).start()
    assert w.api("/api/connect", {}, {"backend": "bridge", "address": f"tcp:127.0.0.1:{srv.getsockname()[1]}"})["ok"]
    assert w.api("/api/ident", {}, {})["2180"].startswith("6180")
    assert w.api("/api/live", {"lids": ["A1"]}, {})["lids"]["A1"]["bytes"][0] >= 0
    assert w.api("/api/console", {}, {"line": "STATUS"})["resp"][-1].startswith("OK")
    assert w.api("/api/serial_log", {"n": ["5"]}, {})["lines"]
    w.api("/api/disconnect", {}, {})


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
