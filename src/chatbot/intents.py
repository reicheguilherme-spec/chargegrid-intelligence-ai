"""
Roteador de intencao (regras + memoria da conversa).

Decide qual consulta de dados a pergunta exige. Se nada casar, a pergunta e tratada como
FORA DO ESCOPO. Perguntas de seguimento ("e a 6?") usam a memoria da conversa.
"""
import re
from dataclasses import dataclass, field

from chatbot.textutil import norm


@dataclass
class Intencao:
    nome: str                      # sessao, status, energia, pico, financeiro, ... fora_escopo, sem_dados, ajuda
    params: dict = field(default_factory=dict)
    seguimento: bool = False       # True quando a pergunta depende da memoria da conversa


# padroes em texto normalizado (minusculo, sem acento)
RE_SEM_DADOS = r"condominio|predio|outra estacao|outro posto|outra unidade|shopping|filial|outras estacoes|posto de"
RE_SESSAO = r"(?:sessao|carro|veiculo)\s*(?:numero|n|no|#)?\s*(\d+)"
RE_SEGUIMENTO = r"\s*(?:e|mas)?\s*(?:a|o|da|do|na|no)?\s*(?:sessao|carro|veiculo)?\s*(\d+)\s*\??\s*"
RE_LISTA = r"todas as sessoes|as sessoes|sessoes de hoje|quantas (?:recargas|sessoes|carros|veiculos)|resumo das sessoes|recargas de hoje"
RE_HORA = r"(?:\bas\s+|\ba\s+|\bde\s+)?\b(\d{1,2})\s*(?:h|:)\s*(\d{2})?\b"
RE_COMPARA = r"compar|baseline|sem ia|com ia|vale a pena|beneficio|ganho"
RE_FINANC = r"fatur|receita|lucro|margem|custo|quanto (?:eu )?(?:ganh|receb)|cobr|tarifa|preco|dinheiro|r\$"
RE_PICO = r"pico|demanda|potencia maxima|limite contratad|potencia contratada"
RE_PREVISAO = r"previs|prever|forecast|confiavel|confiabilidade|erro do modelo|modelo de ia|acerta"
RE_SUSTENT = r"co2|carbono|emiss|sustent|ambient"
RE_BATERIA = r"bateria|armazen|\bsoc\b"
RE_ENERGIA = r"energia|consum|solar|\brede\b|renovav|kwh|gerou|geracao|excedente|desperdic"
RE_AJUDA = r"^(?:oi|ola|ei|bom dia|boa tarde|boa noite)\b|o que voce (?:faz|pode)|\bajuda\b|quem e voce|\bmenu\b"


def detectar(texto: str, memoria: dict) -> Intencao:
    t = norm(texto).strip()

    if re.search(RE_AJUDA, t) and len(t.split()) <= 8:
        return Intencao("ajuda")
    if re.search(RE_SEM_DADOS, t):
        return Intencao("sem_dados", {"motivo": "outros locais, condomínios ou unidades (só existem dados desta estação)"})

    m = re.search(RE_SESSAO, t)
    if m:
        return Intencao("sessao", {"n": int(m.group(1))})

    # seguimento: "e a 6?" depois de uma pergunta sobre sessao
    m = re.fullmatch(RE_SEGUIMENTO, t)
    if m and memoria.get("ultima_intent") == "sessao":
        return Intencao("sessao", {"n": int(m.group(1))}, seguimento=True)

    if re.search(RE_LISTA, t):
        return Intencao("lista_sessoes")

    m = re.search(RE_HORA, t)
    if m and 0 <= int(m.group(1)) <= 23 and (m.group(2) or "h" in t or ":" in t):
        return Intencao("status", {"hh": int(m.group(1)), "mm": int(m.group(2) or 0)})

    for nome, padrao in (
        ("comparativo", RE_COMPARA),
        ("financeiro", RE_FINANC),
        ("pico", RE_PICO),
        ("previsao", RE_PREVISAO),
        ("sustentabilidade", RE_SUSTENT),
        ("bateria", RE_BATERIA),
        ("energia", RE_ENERGIA),
    ):
        if re.search(padrao, t):
            return Intencao(nome)

    return Intencao("fora_escopo")
