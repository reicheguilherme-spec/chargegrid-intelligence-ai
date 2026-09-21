"""
Nucleo do chatbot: junta roteador de intencao, dados da estacao, system prompt, memoria e backend.
"""
from dataclasses import dataclass

from config import RAIZ
from chatbot.dados import DadosEstacao
from chatbot.intents import detectar

CAMINHO_PROMPT = RAIZ / "prompts" / "system_prompt.txt"
MAX_TURNOS_MEMORIA = 8          # quantas trocas (pergunta+resposta) ficam no historico


def carregar_system_prompt() -> str:
    return CAMINHO_PROMPT.read_text(encoding="utf-8")


@dataclass
class Resposta:
    texto: str
    intent: str
    fatos: object
    seguimento: bool


class ChargeGridBot:
    def __init__(self, backend, dados: DadosEstacao = None):
        self.backend = backend
        self.dados = dados or DadosEstacao()
        self.system_prompt = carregar_system_prompt()
        self.historico = []                    # [{"role": "user"|"assistant", "content": str}]
        self.memoria = {"ultima_intent": None, "ultima_sessao": None}

    def perguntar(self, texto: str) -> Resposta:
        intencao = detectar(texto, self.memoria)

        # 1) consulta os dados da estacao (o LLM so pode usar o que vier daqui)
        if intencao.nome in ("fora_escopo", "ajuda", "sem_dados"):
            fatos = intencao.params or {}
        else:
            fatos = self.dados.consultar(intencao.nome, intencao.params)   # None se nao existir (ex.: sessao 9)

        # 2) o backend (LLM ou offline) escreve a resposta
        resposta = self.backend.responder(
            self.system_prompt, self.historico, texto, intencao.nome, fatos, intencao.seguimento)

        # 3) atualiza memoria e historico
        self.historico += [{"role": "user", "content": texto}, {"role": "assistant", "content": resposta}]
        self.historico = self.historico[-2 * MAX_TURNOS_MEMORIA:]
        self.memoria["ultima_intent"] = intencao.nome
        if intencao.nome == "sessao":
            self.memoria["ultima_sessao"] = intencao.params["n"]
        return Resposta(resposta, intencao.nome, fatos, intencao.seguimento)
