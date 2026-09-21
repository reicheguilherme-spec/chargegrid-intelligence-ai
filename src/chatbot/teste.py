"""
Validacao do chatbot com o modelo de teste (tests/modelo_de_teste.json).

Para cada teste: cria um bot NOVO, roda a conversa e confere a ULTIMA resposta:
  * deve_conter        : todos os itens precisam aparecer (numeros aceitam 1 ou 2 casas decimais)
  * deve_conter_algum  : pelo menos um item precisa aparecer
  * nao_deve_conter    : nenhum item pode aparecer
Nota do teste = criterios cumpridos / total; "passou" se todos forem cumpridos.
"""
import csv
import json
import re

from config import RAIZ, DATA_DIR, DOCS_DIR
from chatbot.bot import ChargeGridBot
from chatbot.dados import DadosEstacao
from chatbot.textutil import norm, fmt_br, decimais_ponto

CAMINHO_TESTES = RAIZ / "tests" / "modelo_de_teste.json"
RE_PH = re.compile(r"\{([mst]):([^}]+)\}")


# ------------------------------------------------------------------ placeholders
def _valor(dados: DadosEstacao, tipo: str, spec: str):
    if tipo == "m":                                        # metricas.json: proposta.rede_kwh
        v = dados.m
        for chave in spec.split("."):
            v = v[chave]
        return float(v)
    if tipo == "s":                                        # sessao: 5:kwh_rede
        n, campo = spec.split(":")
        return float(dados.sess.loc[int(n), campo])
    hh, mm, campo = spec.split(":")                        # telemetria: 19:00:ev_kw
    return float(dados.tel[dados.tel.hora == f"{hh}:{mm}"].iloc[0][campo])


def _resolver(texto: str, dados: DadosEstacao) -> str:
    def troca(m):
        *spec, casas = m.group(2).split(":")
        return fmt_br(_valor(dados, m.group(1), ":".join(spec)), int(casas))
    return RE_PH.sub(troca, texto)


def _variantes(item: str, dados: DadosEstacao):
    """Item numerico ({...}) vira variantes aceitas (1 casa e 2 casas); texto vira ele mesmo."""
    m = RE_PH.fullmatch(item)
    if not m:
        return [item]
    *spec, casas = m.group(2).split(":")
    v = _valor(dados, m.group(1), ":".join(spec))
    saidas = {f"{round(v, int(casas)):.{int(casas)}f}", f"{round(v, 2):.2f}".rstrip("0").rstrip("."), f"{v:g}"}
    return sorted(saidas)


def _contem(resposta_norm: str, variante: str) -> bool:
    v = norm(variante)
    if re.fullmatch(r"\d+(?:\.\d+)?", v):                 # numero: nao pode estar colado a outros digitos
        return re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])", resposta_norm) is not None
    return v in resposta_norm


# ------------------------------------------------------------------ execucao
def executar(backend, salvar=True, verbose=True):
    dados = DadosEstacao()
    testes = json.loads(CAMINHO_TESTES.read_text(encoding="utf-8"))["testes"]
    linhas = []
    for t in testes:
        bot = ChargeGridBot(backend, dados)
        resposta = ""
        for pergunta in t["conversa"]:
            resposta = bot.perguntar(pergunta).texto
        rn = decimais_ponto(norm(resposta))

        ok, total, falhas = 0, 0, []
        for item in t.get("deve_conter", []):
            total += 1
            if any(_contem(rn, v) for v in _variantes(item, dados)):
                ok += 1
            else:
                falhas.append(f"faltou: {item}")
        if t.get("deve_conter_algum"):
            total += 1
            if any(norm(x) in rn for x in t["deve_conter_algum"]):
                ok += 1
            else:
                falhas.append(f"faltou algum de: {t['deve_conter_algum']}")
        for item in t.get("nao_deve_conter", []):
            total += 1
            if norm(item) not in rn:
                ok += 1
            else:
                falhas.append(f"não deveria conter: {item}")

        linhas.append({
            "id": t["id"], "tipo": t["tipo"], "pergunta": " | ".join(t["conversa"]),
            "resposta_ideal": _resolver(t["resposta_ideal"], dados), "resposta_obtida": resposta,
            "criterios_ok": ok, "criterios_total": total, "passou": "sim" if ok == total else "NAO",
            "falhas": "; ".join(falhas),
        })
        if verbose:
            print(f"[{'OK ' if ok == total else 'FALHOU'}] {t['id']} ({t['tipo']}): {ok}/{total}"
                  + (f"  -> {'; '.join(falhas)}" if falhas else ""))

    aprovados = sum(1 for l in linhas if l["passou"] == "sim")
    print(f"\nBackend '{backend.nome}': {aprovados}/{len(linhas)} testes aprovados | "
          f"critérios: {sum(l['criterios_ok'] for l in linhas)}/{sum(l['criterios_total'] for l in linhas)}")

    if salvar:
        caminho = DATA_DIR / f"teste_chatbot_{backend.nome}.csv"
        with open(caminho, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            w.writeheader()
            w.writerows(linhas)
        print(f"Resultados gravados em {caminho}")
        gerar_documento_modelo(linhas)
    return linhas


def gerar_documento_modelo(linhas):
    """docs/modelo_de_teste.md: perguntas e respostas ideais (base de avaliacao)."""
    md = ["# Modelo de teste do chatbot ChargeGrid Intelligence", "",
          "Perguntas esperadas e **respostas ideais** (valores preenchidos com os dados reais da simulação). "
          "Cada teste tem critérios automáticos (números e frases que devem ou não aparecer). "
          "Execute com `python src/chat.py --teste`.", "",
          "| ID | Tipo | Pergunta(s) | Resposta ideal |", "|---|---|---|---|"]
    for l in linhas:
        md.append(f"| {l['id']} | {l['tipo']} | {l['pergunta'].replace('|', '→')} | {l['resposta_ideal']} |")
    (DOCS_DIR / "modelo_de_teste.md").write_text("\n".join(md) + "\n", encoding="utf-8")
