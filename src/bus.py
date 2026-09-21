"""
Barramento de mensagens no estilo MQTT (publicar / assinar topicos).

Na simulacao ele roda dentro do proprio Python. No hardware real, basta trocar
esta classe por um cliente paho-mqtt apontando para um broker (ex.: Mosquitto):
os topicos e os payloads JSON continuam exatamente os mesmos.
"""
import json
from pathlib import Path

from config import hhmm


def topico_casa(padrao: str, topico: str) -> bool:
    """Casamento de topicos MQTT: '+' = um nivel, '#' = todos os niveis restantes."""
    p, t = padrao.split("/"), topico.split("/")
    for i, seg in enumerate(p):
        if seg == "#":
            return True
        if i >= len(t):
            return False
        if seg != "+" and seg != t[i]:
            return False
    return len(p) == len(t)


class BarramentoMQTT:
    def __init__(self):
        self._assinaturas = []   # lista de (padrao, callback)
        self.log = []            # historico de todas as mensagens
        self.agora_h = 0.0       # relogio da simulacao (hora decimal)

    def assinar(self, padrao: str, callback):
        self._assinaturas.append((padrao, callback))

    def publicar(self, topico: str, payload: dict):
        self.log.append({"hora": hhmm(self.agora_h), "topico": topico, "payload": payload})
        for padrao, callback in self._assinaturas:
            if topico_casa(padrao, topico):
                callback(topico, payload)

    def salvar_jsonl(self, caminho: Path):
        """Grava o log de mensagens: uma mensagem JSON por linha."""
        with open(caminho, "w", encoding="utf-8") as f:
            for msg in self.log:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
