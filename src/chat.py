"""
Chatbot ChargeGrid Intelligence - ponto de entrada.

    python src/chat.py                 conversa no terminal
    python src/chat.py --web           interface web em http://localhost:8000
    python src/chat.py --demo          roda uma conversa de demonstracao (e salva em docs/)
    python src/chat.py --teste         roda o modelo de teste (tests/modelo_de_teste.json)

Backend (quem escreve as respostas):
    --backend auto     (padrao) usa o Gemini se a variavel GEMINI_API_KEY existir; senao, modo offline
    --backend gemini   LLM real (exige GEMINI_API_KEY)
    --backend offline  respondedor por templates (sem internet, resultado reproduzivel)

Antes de tudo, gere os dados da estacao:  python src/main.py
"""
import argparse
import os
import sys

from config import DOCS_DIR
from chatbot.backends import BackendGemini, BackendOffline
from chatbot.bot import ChargeGridBot

PERGUNTAS_DEMO = [
    "Oi, o que você faz?",
    "Quanto de energia da rede a estação consumiu hoje e quanto foi solar?",
    "Como foi a sessão 5?",
    "E a 6?",
    "Quanto faturei hoje e qual foi a margem?",
    "Como estava a estação às 19:00?",
    "Vale a pena usar IA e bateria? Compare com o cenário sem IA.",
    "Qual é a capital da França?",
    "Quantos carros o condomínio Solar Park recarregou este mês?",
]


def escolher_backend(nome: str):
    if nome == "offline":
        return BackendOffline()
    if nome == "gemini":
        return BackendGemini()
    if os.environ.get("GEMINI_API_KEY"):
        return BackendGemini()
    print("ℹ️  GEMINI_API_KEY não definida: usando o modo OFFLINE (respostas por templates, sem LLM).\n"
          "   Para usar o LLM real defina a chave (veja o README) ou rode com --backend gemini.\n")
    return BackendOffline()


def demo(bot, backend):
    md = [f"# Exemplo de conversa (backend: {backend.nome})", "",
          "Gerado por `python src/chat.py --demo`. Dados simulados.", ""]
    for p in PERGUNTAS_DEMO:
        r = bot.perguntar(p)
        print(f"\n👤 Operador: {p}\n🤖 Assistente: {r.texto}")
        md += [f"**👤 Operador:** {p}", "", f"**🤖 Assistente** _(tema: {r.intent})_: {r.texto}", ""]
    caminho = DOCS_DIR / f"exemplo_conversa_{backend.nome}.md"
    caminho.write_text("\n".join(md), encoding="utf-8")
    print(f"\nConversa salva em {caminho}")


def terminal(bot, backend):
    print(f"ChargeGrid Assistant (backend: {backend.nome}). Digite 'sair' para encerrar, '/limpar' para zerar a memória.\n")
    while True:
        try:
            texto = input("👤 Operador: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not texto:
            continue
        if texto.lower() in ("sair", "exit", "quit"):
            break
        if texto == "/limpar":
            bot.historico.clear()
            bot.memoria.update({"ultima_intent": None, "ultima_sessao": None})
            print("Memória da conversa limpa.\n")
            continue
        try:
            print(f"🤖 Assistente: {bot.perguntar(texto).texto}\n")
        except RuntimeError as e:
            print(f"⚠️  {e}\n")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Chatbot ChargeGrid Intelligence")
    ap.add_argument("--backend", choices=["auto", "offline", "gemini"], default="auto")
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--demo", action="store_true", help="conversa de demonstração")
    grupo.add_argument("--teste", action="store_true", help="roda o modelo de teste")
    grupo.add_argument("--web", action="store_true", help="interface web")
    ap.add_argument("--porta", type=int, default=8000)
    a = ap.parse_args()

    try:
        backend = escolher_backend(a.backend)
    except RuntimeError as e:
        raise SystemExit(f"⚠️  {e}")

    if a.teste:
        from chatbot import teste
        try:
            teste.executar(backend)
        except RuntimeError as e:
            raise SystemExit(f"⚠️  {e}")
    elif a.web:
        from chatbot.web import servir
        servir(backend, a.porta)
    else:
        bot = ChargeGridBot(backend)
        try:
            demo(bot, backend) if a.demo else terminal(bot, backend)
        except RuntimeError as e:
            raise SystemExit(f"⚠️  {e}")


if __name__ == "__main__":
    main()
