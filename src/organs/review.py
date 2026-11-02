"""Local keep/reject review. Shows original, cutout, and class mask side by side.

Keys: K keep, R reject, Left/Right move. Decisions are written straight to the manifest.
Serves on 127.0.0.1 only.
"""
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import numpy as np
from PIL import Image

from . import manifest, paths
from .classes import CLASSES, SWATCH

PAGE = """<!doctype html><meta charset=utf-8><title>organs review</title>
<style>
body{margin:0;font:14px system-ui;background:#111;color:#ddd;display:flex;flex-direction:column;height:100vh}
header{padding:10px 16px;display:flex;gap:16px;align-items:center;border-bottom:1px solid #333}
main{flex:1;display:flex;gap:8px;padding:8px;min-height:0}
figure{margin:0;flex:1;display:flex;flex-direction:column;min-width:0}
figure img{flex:1;min-height:0;object-fit:contain;background:#222}
figcaption{padding:4px;color:#888}
button{font:inherit;padding:8px 18px;border:0;border-radius:4px;cursor:pointer}
.keep{background:#2e7d32;color:#fff}.reject{background:#c62828;color:#fff}
.tag{padding:2px 8px;border-radius:3px;background:#333}
</style>
<header><b id=pos></b><span id=meta></span><span style=flex:1></span>
<button class=reject onclick="decide('reject')">Reject (R)</button>
<button class=keep onclick="decide('keep')">Keep (K)</button></header>
<main><figure><img id=raw><figcaption>original</figcaption></figure>
<figure><img id=cut><figcaption>cutout</figcaption></figure>
<figure><img id=mask><figcaption>mask</figcaption></figure></main>
<script>
let q=[],i=0;
const $=id=>document.getElementById(id);
async function load(){q=await (await fetch('/api/queue')).json();i=0;show()}
function show(){
  if(!q.length){$('pos').textContent='queue empty';return}
  i=Math.max(0,Math.min(i,q.length-1));const r=q[i];
  $('pos').textContent=(i+1)+' / '+q.length;
  $('meta').innerHTML=`<span class=tag>${r.class}</span> <span class=tag>${r.status}${r.reason?': '+r.reason:''}</span> ${r.source} ${r.license} - ${r.title}`;
  for(const k of ['raw','cut','mask'])$(k).src='/'+k+'/'+r.id;
}
async function decide(s){
  if(!q.length)return;
  await fetch('/api/decide',{method:'POST',body:JSON.stringify({id:q[i].id,status:s})});
  q.splice(i,1);show();
}
addEventListener('keydown',e=>{
  if(e.key=='k')decide('keep');else if(e.key=='r')decide('reject');
  else if(e.key=='ArrowRight'){i++;show()}else if(e.key=='ArrowLeft'){i--;show()}
});
load();
</script>"""


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _colored_mask(rid: str) -> bytes:
    m = np.asarray(Image.open(paths.MASKS / f"{rid}.png"))
    out = np.full((*m.shape, 3), 40, dtype=np.uint8)
    for i, c in enumerate(CLASSES, 1):
        out[m == i] = SWATCH[c]
    return _png(Image.fromarray(out))


def make_handler(status: str):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body: bytes, ctype: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                return self._send(PAGE.encode(), "text/html; charset=utf-8")
            if path == "/api/queue":
                rows = [r for r in manifest.load().values() if r["status"] == status]
                return self._send(json.dumps(rows).encode(), "application/json")
            kind, _, rid = path.strip("/").partition("/")
            rec = manifest.load().get(rid)
            if not rec:
                return self._send(b"not found", "text/plain", 404)
            try:
                if kind == "raw":
                    img = Image.open(paths.DATA / rec["path"]).convert("RGB")
                    img.thumbnail((900, 900))
                    return self._send(_png(img), "image/png")
                if kind == "cut":
                    return self._send((paths.CUTOUTS / f"{rid}.jpg").read_bytes(), "image/jpeg")
                if kind == "mask":
                    return self._send(_colored_mask(rid), "image/png")
            except FileNotFoundError:
                pass
            self._send(b"not found", "text/plain", 404)

        def do_POST(self):
            if self.path != "/api/decide":
                return self._send(b"not found", "text/plain", 404)
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if body["status"] not in {"keep", "reject"}:
                return self._send(b"bad status", "text/plain", 400)
            manifest.update(body["id"], status=body["status"])
            self._send(b"ok", "text/plain")

    return H


def serve(status: str = "cut", port: int = 8765) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(status))
    print(f"review {status!r} at http://127.0.0.1:{port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
