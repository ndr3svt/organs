"""Local keep/reject review. Shows original, cutout, and class mask side by side.

Keys: K keep, R reject, Left/Right move, C reset the cutout to automatic.
Click the organ in the original to cut out just that (SAM); Shift-click marks a spot that is not the organ.
Decisions are written straight to the manifest. Serves on 127.0.0.1 only.
"""
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import numpy as np
from PIL import Image

from . import cutout, manifest, paths
from .classes import CLASSES, SWATCH

_lock = threading.Lock()  # one recut at a time: the segmentation sessions are shared

PAGE = """<!doctype html><meta charset=utf-8><title>organs review</title>
<style>
body{margin:0;font:14px system-ui;background:#111;color:#ddd;display:flex;flex-direction:column;height:100vh}
header{padding:10px 16px;display:flex;gap:16px;align-items:center;border-bottom:1px solid #333}
main{flex:1;display:flex;gap:8px;padding:8px;min-height:0}
figure{margin:0;flex:1;display:flex;flex-direction:column;min-width:0;position:relative}
figure img{flex:1;min-height:0;object-fit:contain;background:#222}
#raw{cursor:crosshair}
.dot{position:absolute;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;border:2px solid #fff;pointer-events:none}
.dot.pos{background:#43a047}.dot.neg{background:#e53935}
#busy{color:#ffb300}
figcaption{padding:4px;color:#888}
button{font:inherit;padding:8px 18px;border:0;border-radius:4px;cursor:pointer}
.keep{background:#2e7d32;color:#fff}.reject{background:#c62828;color:#fff}
.tag{padding:2px 8px;border-radius:3px;background:#333}
</style>
<header><b id=pos></b><span id=meta></span><span id=busy></span><span style=flex:1></span><span style=color:#777>click organ / shift-click not organ / C reset</span>
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
  if(!r.pts&&r.points)r.pts=r.points;
  $('pos').textContent=(i+1)+' / '+q.length;
  $('meta').innerHTML=`<span class=tag>${r.class}</span> <span class=tag>${r.status}${r.reason?': '+r.reason:''}</span> ${r.source} ${r.license} - ${r.title}`;
  for(const k of ['raw','cut','mask'])$(k).src='/'+k+'/'+r.id+'?v='+(r.v||0);
  $('busy').textContent='';drawDots();
}
// rectangle the image actually occupies inside its object-fit:contain box
function imgRect(){
  const im=$('raw'),b=im.getBoundingClientRect(),nw=im.naturalWidth,nh=im.naturalHeight;
  const s=Math.min(b.width/nw,b.height/nh),w=nw*s,h=nh*s;
  return{b,x:(b.width-w)/2,y:(b.height-h)/2,w,h};
}
function drawDots(){
  document.querySelectorAll('.dot').forEach(d=>d.remove());
  const r=q[i];if(!r||!r.pts)return;
  const R=imgRect(),fig=$('raw').parentElement.getBoundingClientRect();
  for(const [x,y,l] of r.pts){
    const d=document.createElement('div');d.className='dot '+(l?'pos':'neg');
    d.style.left=(R.b.left-fig.left+R.x+x*R.w)+'px';d.style.top=(R.b.top-fig.top+R.y+y*R.h)+'px';
    $('raw').parentElement.appendChild(d);
  }
}
async function recut(){
  const r=q[i];$('busy').textContent='cutting... (first click loads the model, ~10 s)';
  try{
    const res=await fetch('/api/recut',{method:'POST',body:JSON.stringify({id:r.id,points:r.pts||[]})});
    if(!res.ok)throw new Error('HTTP '+res.status);
    Object.assign(r,await res.json());r.v=Date.now();
  }catch(err){$('busy').textContent='recut failed: '+err.message;return}
  show();
}
$('raw').addEventListener('click',e=>{
  const r=q[i];if(!r)return;
  const R=imgRect(),x=(e.clientX-R.b.left-R.x)/R.w,y=(e.clientY-R.b.top-R.y)/R.h;
  if(x<0||x>1||y<0||y>1)return;
  (r.pts=r.pts||[]).push([x,y,e.shiftKey?0:1]);
  drawDots();recut();
});
addEventListener('resize',drawDots);
$('raw').addEventListener('load',drawDots);
async function decide(s){
  if(!q.length)return;
  try{
    const r=await fetch('/api/decide',{method:'POST',body:JSON.stringify({id:q[i].id,status:s})});
    if(!r.ok)throw new Error('HTTP '+r.status);
  }catch(err){
    $('meta').innerHTML='<b style=color:#ef5350>not saved: '+err.message+' - is `organs review` still running?</b>';
    return;
  }
  q.splice(i,1);show();
}
addEventListener('keydown',e=>{
  const k=e.key.toLowerCase();
  if(k=='k')decide('keep');else if(k=='r')decide('reject');
  else if(k=='c'&&q[i]){q[i].pts=[];recut()}
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
            self.send_header("Cache-Control", "no-store")
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
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/api/decide":
                if body["status"] not in {"keep", "reject"}:
                    return self._send(b"bad status", "text/plain", 400)
                with _lock:
                    manifest.update(body["id"], status=body["status"])
                return self._send(b"ok", "text/plain")
            if self.path == "/api/recut":
                with _lock:
                    records = manifest.load()
                    rec = records.get(body["id"])
                    if not rec:
                        return self._send(b"not found", "text/plain", 404)
                    cutout.recut(rec, [tuple(p) for p in body["points"]])
                    manifest.save(records)
                out = {k: rec[k] for k in ("status", "reason", "points")}
                return self._send(json.dumps(out).encode(), "application/json")
            self._send(b"not found", "text/plain", 404)

    return H


def serve(status: str = "cut", port: int = 8765) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(status))
    print(f"review {status!r} at http://127.0.0.1:{port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
