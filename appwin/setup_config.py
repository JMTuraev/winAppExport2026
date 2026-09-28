"""Called by the Windows installer: writes/merges AppWin\\config.json (UTF-8, forward-slash paths).
usage: python -m appwin.setup_config <config.json> server  data_dir=<path> [backup_dir=<path>]
       python -m appwin.setup_config <config.json> client  server_url=http://IP:8765"""
import json, sys
from pathlib import Path

DEFAULTS = {
    "server": {"mode": "server", "host": "0.0.0.0", "port": 8765, "open_browser": False, "backup_dir": "", "download_dir": "", "server_url": ""},
    "client": {"mode": "client", "server_url": "", "download_dir": "", "auto_update": True},
}

def main(argv: list[str]) -> int:
    if len(argv) < 2: print(__doc__); return 2
    path, mode = Path(argv[0]), argv[1]
    cfg = {}
    if path.exists():
        try: cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception: cfg = {}
    out = {**DEFAULTS.get(mode, {}), **cfg, "mode": mode}
    for kv in argv[2:]:
        if "=" not in kv: continue
        k, v = kv.split("=", 1)
        v = v.strip().strip('"')
        if k in ("data_dir", "backup_dir", "download_dir"): v = v.replace("\\", "/").rstrip("/")
        if k == "server_url":
            v = v.rstrip("/")
            if v and not v.startswith("http"): v = "http://" + v
            if v and v.count(":") < 2: v += ":8765"
        if k == "port":
            try: v = int(v)
            except ValueError: continue
        if v == "" and k in cfg: continue          # empty field on the page keeps the old value
        out[k] = v
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("config:", path); print(json.dumps(out, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
