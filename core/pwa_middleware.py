"""App en la pantalla de inicio del iPhone (31-oct-2026).

Dos cosas en todas las páginas HTML, sin tocar cada plantilla:

1. El icono y el nombre: si la página no trae ``apple-touch-icon``, se añade
   el de la app (antes, al guardar Ahora en la pantalla de inicio salía solo
   una letra).
2. Un aviso de carga: abierta desde la pantalla de inicio, la app va a
   pantalla completa, sin barra del navegador, y al tocar un botón no se veía
   nada hasta que llegaba la página. Ahora sale una barra arriba y un
   "Cargando…" si tarda.
"""

from django.templatetags.static import static

MARCA = b'data-pwa-app="1"'


def _cabecera():
    return (
        f'<link rel="apple-touch-icon" sizes="180x180" href="{static("icons/apple-touch-icon.png")}" data-pwa-app="1">'
        f'<link rel="icon" type="image/png" sizes="32x32" href="{static("icons/favicon-32.png")}">'
        f'<link rel="manifest" href="{static("manifest.json")}">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-title" content="Gym">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
    ).encode()


CARGA = b"""<div id="pwa-carga" role="status" aria-live="polite" style="position:fixed;left:50%;top:calc(env(safe-area-inset-top, 0px) + 72px);transform:translateX(-50%);z-index:2147483647;pointer-events:none;display:none;align-items:center;gap:10px;padding:10px 16px;border-radius:99px;background:rgba(10,14,16,.96);border:1px solid rgba(66,228,160,.5);box-shadow:0 6px 24px rgba(0,0,0,.5);color:#42e4a0;font:600 14px/1 -apple-system,system-ui,sans-serif"><span style="width:16px;height:16px;border-radius:50%;border:2px solid rgba(66,228,160,.25);border-top-color:#42e4a0;animation:pwaGira .7s linear infinite"></span>Cargando\xe2\x80\xa6</div>
<style>@keyframes pwaGira{to{transform:rotate(360deg)}}</style>
<script>(function(){
// 31-oct-2026: un aviso centrado bajo la parte de arriba (la barra fina
// quedaba tapada por el difuminado superior de la pantalla).
var b=document.getElementById('pwa-carga'),tm=null;
function on(){if(!b)return;clearTimeout(tm);tm=setTimeout(function(){b.style.display='flex';tm=setTimeout(off,15000);},150);}
function off(){if(!b)return;clearTimeout(tm);b.style.display='none';}
document.addEventListener('click',function(e){
  if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey)return;
  var a=e.target.closest&&e.target.closest('a[href]');if(!a)return;
  var h=a.getAttribute('href')||'';
  if(!h||h.charAt(0)==='#'||/^(javascript|mailto|tel|sms):/i.test(h)||a.target==='_blank'||a.hasAttribute('download'))return;
  try{var u=new URL(a.href,location.href);if(u.origin!==location.origin)return;if(u.pathname===location.pathname&&u.search===location.search&&u.hash)return;}catch(_){return;}
  on();
});
document.addEventListener('submit',function(e){if(!e.defaultPrevented&&!(e.target&&e.target.target==='_blank'))setTimeout(function(){if(!e.defaultPrevented)on();},0);});
window.addEventListener('pageshow',off);
})();</script>"""


class PwaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            return self._anadir(response)
        except Exception:  # noqa: BLE001 — nunca romper una página por esto
            return response

    def _anadir(self, response):
        tipo = response.get('Content-Type', '')
        if (
            response.status_code != 200 or getattr(response, 'streaming', False)
            or 'text/html' not in tipo or response.get('Content-Encoding')
        ):
            return response
        html = response.content
        if MARCA in html or b'</head>' not in html:
            return response
        cab = b'' if b'apple-touch-icon' in html else _cabecera()
        html = html.replace(b'</head>', cab + b'<meta name="pwa-app" ' + MARCA + b'></head>', 1)
        if b'</body>' in html:
            i = html.rfind(b'</body>')
            html = html[:i] + CARGA + html[i:]
        response.content = html
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(html))
        return response
