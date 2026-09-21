"""
Interface web do chatbot (somente biblioteca padrao do Python).

    python src/chat.py --web        ->  abre http://localhost:8000

Cada aba do navegador tem seu proprio historico (memoria de contexto).
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from chatbot.bot import ChargeGridBot
from chatbot.dados import DadosEstacao

PAGINA = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ChargeGrid Assistant</title>
<style>
:root{--bg:#f4f6fb;--card:#fff;--txt:#1f2933;--mut:#66788a;--pri:#c2185b;--ok:#2e9e6b;--sol:#f5a623}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--txt)}
header{background:#1f3f8f;color:#fff;padding:14px 22px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
header h1{font-size:18px;margin:0}header small{opacity:.85}
.badge{background:var(--pri);border-radius:999px;padding:3px 12px;font-size:12px;font-weight:600}
main{max-width:1100px;margin:16px auto;padding:0 14px;display:grid;grid-template-columns:1fr 300px;gap:16px}
@media(max-width:820px){main{grid-template-columns:1fr}}
.card{background:var(--card);border-radius:14px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
#chat{height:62vh;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px}
.msg{max-width:85%;padding:10px 14px;border-radius:14px;white-space:pre-wrap;line-height:1.45;font-size:15px}
.user{align-self:flex-end;background:var(--pri);color:#fff;border-bottom-right-radius:4px}
.bot{align-self:flex-start;background:#eef1f7;border-bottom-left-radius:4px}
.tag{font-size:11px;color:var(--mut);margin-top:4px}
form{display:flex;gap:8px;padding:12px;border-top:1px solid #e5e9f0}
input{flex:1;padding:12px;border:1px solid #cfd8e3;border-radius:10px;font-size:15px}
button{background:var(--pri);color:#fff;border:0;border-radius:10px;padding:0 20px;font-weight:600;cursor:pointer}
.chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 12px 12px}
.chip{background:#fff;border:1px solid #cfd8e3;color:var(--txt);border-radius:999px;padding:6px 12px;font-size:13px;font-weight:500}
.chip:hover{border-color:var(--pri);color:var(--pri)}
aside{padding:16px}aside h2{font-size:14px;margin:0 0 10px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.kpi{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eef1f5;font-size:14px}
.kpi b{font-variant-numeric:tabular-nums}.aviso{font-size:12px;color:var(--mut);margin-top:12px}
</style></head><body>
<header><div><h1>⚡ ChargeGrid Assistant</h1><small>Estação SolarCharge AI · EV Challenge 2026</small></div>
<span class="badge" id="badge">…</span></header>
<main>
<section class="card"><div id="chat"></div>
<div class="chips" id="chips"></div>
<form id="f"><input id="q" autocomplete="off" placeholder="Pergunte sobre energia, sessões, faturamento, previsão…"><button>Enviar</button></form></section>
<aside class="card"><h2>Resumo do dia (simulado)</h2><div id="kpis"></div>
<p class="aviso">Dados gerados por simulação. Valores em R$ e CO₂ são ilustrativos.</p></aside>
</main>
<script>
const cliente=Math.random().toString(36).slice(2), chat=document.getElementById('chat');
const sugestoes=["Quanto de energia da rede consumimos hoje?","Como foi a sessão 5?","E a 6?","Quanto faturei e qual a margem?","Como estava a estação às 19:00?","Vale a pena usar IA e bateria?","Qual é a capital da França?"];
function add(t,c,tag){const d=document.createElement('div');d.className='msg '+c;d.textContent=t;
 if(tag){const s=document.createElement('div');s.className='tag';s.textContent=tag;d.appendChild(s)}
 chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d}
async function enviar(txt){add(txt,'user');const w=add('…','bot');
 try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mensagem:txt,cliente})});
 const j=await r.json();w.remove();add(j.resposta,'bot','tema: '+j.intent)}catch(e){w.textContent='Erro: '+e}}
document.getElementById('f').onsubmit=e=>{e.preventDefault();const i=document.getElementById('q');if(!i.value.trim())return;const v=i.value;i.value='';enviar(v)};
sugestoes.forEach(s=>{const b=document.createElement('button');b.type='button';b.className='chip';b.textContent=s;b.onclick=()=>enviar(s);document.getElementById('chips').appendChild(b)});
fetch('/api/resumo').then(r=>r.json()).then(j=>{document.getElementById('badge').textContent='LLM: '+j.backend;
 document.getElementById('kpis').innerHTML=j.kpis.map(k=>`<div class="kpi"><span>${k[0]}</span><b>${k[1]}</b></div>`).join('')});
add('Olá! Sou o assistente do ChargeGrid Intelligence. Pergunte sobre energia, sessões, faturamento ou previsão solar.','bot');
</script></body></html>"""


def servir(backend, porta=8000, abrir=True):
    dados = DadosEstacao()
    bots = {}
    p, b = dados.m["proposta"], dados.m["baseline"]
    kpis = [
        ["Energia entregue", f"{p['energia_entregue_aos_veiculos_kwh']:g} kWh"],
        ["Fração renovável", f"{p['fracao_renovavel_pct']:g} %"],
        ["Energia da rede", f"{p['rede_kwh']:g} kWh"],
        ["Pico da rede", f"{p['pico_rede_kw']:g} kW"],
        ["Faturamento", f"R$ {p['receita_faturada_rs']:g}"],
        ["Margem", f"R$ {p['margem_rs']:g}"],
        ["Metas de carga", p["metas_atingidas"]],
    ]

    class Handler(BaseHTTPRequestHandler):
        def _json(self, obj, code=200):
            corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            if self.path == "/api/resumo":
                return self._json({"backend": backend.nome, "kpis": kpis})
            corpo = PAGINA.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_POST(self):
            if self.path != "/api/chat":
                return self._json({"erro": "rota inexistente"}, 404)
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n).decode("utf-8"))
            bot = bots.setdefault(req.get("cliente", "x"), ChargeGridBot(backend, dados))
            try:
                r = bot.perguntar(req["mensagem"])
                self._json({"resposta": r.texto, "intent": r.intent})
            except RuntimeError as e:
                self._json({"resposta": f"⚠️ {e}", "intent": "erro"})

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    url = f"http://localhost:{porta}"
    print(f"Chatbot no ar em {url}  (backend: {backend.nome})  —  Ctrl+C para parar")
    if abrir:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
