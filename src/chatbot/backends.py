"""
Backends do chatbot (quem escreve a resposta):

  * BackendGemini  : LLM real (Google Gemini via API REST). Usa system prompt + historico + dados.
  * BackendOffline : respondedor deterministico por templates. NAO e um LLM: serve para rodar a
                     demonstracao e os testes sem internet/chave e com resultado reproduzivel.

Ambos recebem exatamente as mesmas entradas (system prompt, historico, pergunta, fatos).
"""
import json
import os
import urllib.error
import urllib.request

from chatbot.textutil import fmt_br as f


# =====================================================================
def formatar_fatos(intent: str, fatos) -> str:
    """Bloco de dados injetado na mensagem do usuario (a unica fonte de numeros do LLM)."""
    linhas = ["[DADOS DA ESTAÇÃO — use somente estes valores]", f"tema: {intent}"]
    if intent == "fora_escopo":
        linhas.append("Nenhum dado disponível: o assunto está fora do escopo do assistente.")
    elif intent == "ajuda":
        linhas.append("O usuário pediu ajuda: apresente o que você pode responder.")
    elif fatos is None:
        linhas.append("Nenhum dado disponível para este pedido (sessão, horário ou período inexistente na simulação).")
    elif intent == "sem_dados":
        linhas.append(f"Nenhum dado disponível: {fatos.get('motivo', 'assunto sem dados')}.")
    else:
        for k, v in fatos.items():
            linhas.append(f"- {k}: {v}")
    return "\n".join(linhas)


# =====================================================================
class BackendGemini:
    nome = "gemini"

    def __init__(self, api_key=None, modelo=None, temperatura=0.2, max_tokens=1500, timeout=45):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Defina a variável de ambiente GEMINI_API_KEY (chave gratuita em aistudio.google.com).")
        self.modelo = modelo or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.temperatura, self.max_tokens, self.timeout = temperatura, max_tokens, timeout

    def responder(self, system_prompt, historico, pergunta, intent, fatos, seguimento=False):
        contents = [{"role": "user" if h["role"] == "user" else "model", "parts": [{"text": h["content"]}]}
                    for h in historico]
        mensagem = f"{pergunta}\n\n{formatar_fatos(intent, fatos)}"
        contents.append({"role": "user", "parts": [{"text": mensagem}]})
        corpo = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": self.temperatura, "maxOutputTokens": self.max_tokens},
        }
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.modelo}:generateContent",
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                dados = json.loads(r.read().decode("utf-8"))
            return dados["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Erro da API Gemini ({e.code}): {e.read().decode('utf-8', 'ignore')[:300]}") from e
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Resposta inesperada da API Gemini: {str(dados)[:300]}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Sem conexão com a API Gemini: {e.reason}") from e


# =====================================================================
class BackendOffline:
    nome = "offline"

    def responder(self, system_prompt, historico, pergunta, intent, fatos, seguimento=False):
        if intent == "fora_escopo":
            return ("Sou o assistente do ChargeGrid Intelligence e só respondo sobre a operação desta estação de "
                    "recarga: energia, sessões, faturamento, pico de demanda, previsão solar e comparação com e sem IA. "
                    "Esse assunto está fora do meu escopo. Quer um resumo do dia?")
        if intent == "ajuda":
            return ("Olá! Sou o assistente do ChargeGrid Intelligence. Posso informar: energia do dia (solar, bateria, "
                    "rede), pico de demanda, detalhes de cada sessão de recarga, faturamento e margem, previsão solar, "
                    "estado da estação em um horário (ex.: 19:00) e a comparação com e sem IA. O que você quer saber?")
        if intent == "sem_dados" or fatos is None:
            motivo = (fatos or {}).get("motivo", "esse pedido (sessão, horário ou período inexistente)")
            return (f"Não tenho dados sobre {motivo}. Só disponho dos dados da estação simulada SolarCharge AI "
                    f"(1 dia, 6 sessões). Posso responder algo sobre ela?")
        return getattr(self, f"_{intent}")(fatos, seguimento)

    # ---- templates por tema ----
    @staticmethod
    def _energia(d, _):
        return (f"Hoje a estação entregou {f(d['energia_entregue_aos_veiculos_kwh'])} kWh aos veículos: "
                f"{f(d['energia_solar_direta_kwh'])} kWh de solar direto, {f(d['energia_da_bateria_kwh'])} kWh vindos da "
                f"bateria e {f(d['energia_da_rede_kwh'])} kWh da rede. Isso dá {f(d['fracao_renovavel_pct'])}% de energia "
                f"renovável. A usina gerou {f(d['energia_gerada_pela_usina_solar_kwh'])} kWh e "
                f"{f(d['excedente_solar_nao_aproveitado_kwh'])} kWh de excedente não foram aproveitados. (Dados simulados.)")

    @staticmethod
    def _pico(d, _):
        return (f"O pico de potência da rede foi {f(d['pico_de_potencia_da_rede_kw'])} kW às {d['hora_do_pico']}, contra "
                f"{f(d['pico_no_cenario_sem_ia_kw'])} kW sem IA ({f(d['reducao_do_pico_pct'], 0)}% menor). Isso importa "
                f"porque a potência contratada é {f(d['potencia_contratada_com_a_concessionaria_kw'], 0)} kW: quanto menor o "
                f"pico, mais folga na instalação e menor o custo de demanda.")

    @staticmethod
    def _financeiro(d, _):
        return (f"Faturamento do dia: R$ {f(d['receita_faturada_rs'], 2)} (energia entregue × R$ "
                f"{f(d['preco_de_venda_rs_por_kwh'], 2)}/kWh). Custo da energia comprada da rede: R$ "
                f"{f(d['custo_da_energia_da_rede_rs'], 2)}. Margem: R$ {f(d['margem_do_dia_rs'], 2)}. Sem a IA o custo da rede "
                f"seria R$ {f(d['custo_da_rede_sem_ia_rs'], 2)}, ou seja, uma economia de R$ "
                f"{f(d['economia_do_dia_com_ia_rs'], 2)} no dia. Valores ilustrativos de uma simulação.")

    @staticmethod
    def _previsao(d, _):
        return (f"O modelo de IA prevê a geração solar com MAE de {f(d['MAE_kw'], 2)} kW, RMSE de {f(d['RMSE_kw'], 2)} kW e "
                f"R² de {f(d['R2'], 2)}, medidos em {d['dias_de_teste_nunca_vistos']} dias de teste que não entraram no "
                f"treino. O erro médio na energia diária é {f(d['erro_medio_na_energia_diaria_pct'])}%. É um modelo simples "
                f"(regressão linear) treinado com dados simulados; em campo é preciso revalidar com dados reais.")

    @staticmethod
    def _status(d, _):
        n = d["veiculos_conectados"]
        return (f"Às {d['hora']} havia {n} veículo{'s' if n != 1 else ''} conectado{'s' if n != 1 else ''}, recebendo "
                f"{f(d['potencia_total_para_veiculos_kw'])} kW no total: {f(d['solar_para_veiculos_kw'])} kW de solar, "
                f"{f(d['bateria_para_veiculos_kw'])} kW da bateria e {f(d['rede_para_veiculos_kw'])} kW da rede. A geração "
                f"solar era {f(d['geracao_solar_kw'])} kW e a bateria estava com {f(d['soc_da_bateria_pct'])}% de carga.")

    @staticmethod
    def _sessao(d, seg):
        ini = "Continuando sobre as sessões: " if seg else ""
        return (f"{ini}Sessão {d['sessao']} (porta {d['porta']}, {d['veiculo']}): chegou às {d['chegada']} e saiu às "
                f"{d['saida']}; SoC de {d['soc_inicial_pct']}% para {f(d['soc_final_pct'], 0)}% (meta {d['soc_alvo_pct']}%, "
                f"atingida: {d['meta_atingida']}). Energia: {f(d['energia_solar_kwh'])} kWh de solar, "
                f"{f(d['energia_da_bateria_kwh'])} kWh da bateria e {f(d['energia_da_rede_kwh'])} kWh da rede "
                f"({f(d['renovavel_pct'])}% renovável); faturamento de R$ {f(d['faturamento_rs'], 2)}. {d['explicacao']}")

    @staticmethod
    def _lista_sessoes(d, _):
        linhas = [f"Hoje foram {d['total_de_sessoes']} sessões:"]
        for k, v in d.items():
            if k.startswith("sessao_"):
                linhas.append(f"• Sessão {k.split('_')[1]}: {v}")
        return "\n".join(linhas)

    @staticmethod
    def _comparativo(d, _):
        return (f"Comparando com o cenário sem IA e sem bateria (mesmo dia e mesmas sessões): a energia da rede caiu "
                f"{f(d['reducao_da_energia_da_rede_pct'])}% (de {f(d['energia_da_rede_sem_ia_kwh'])} para "
                f"{f(d['energia_da_rede_com_ia_kwh'])} kWh), a fração renovável subiu de "
                f"{f(d['fracao_renovavel_sem_ia_pct'])}% para {f(d['fracao_renovavel_com_ia_pct'])}% "
                f"(+{f(d['ganho_de_fracao_renovavel_pontos_percentuais'])} p.p.) e o pico da rede caiu "
                f"{f(d['reducao_do_pico_pct'], 0)}%. Economia de R$ {f(d['economia_no_custo_da_rede_rs'], 2)} no dia e "
                f"{f(d['co2_evitado_kg'], 2)} kg de CO₂ evitados; metas de carga atingidas: "
                f"{d['metas_de_carga_atingidas_com_ia']}. (Simulação.)")

    @staticmethod
    def _sustentabilidade(d, _):
        return (f"A energia da rede nas recargas gerou {f(d['co2_da_rede_com_ia_kg'], 2)} kg de CO₂ com a IA, contra "
                f"{f(d['co2_da_rede_sem_ia_kg'], 2)} kg sem ela: {f(d['co2_evitado_kg'], 2)} kg evitados no dia. A fração "
                f"renovável foi {f(d['fracao_renovavel_pct'])}%. O fator de emissão ({f(d['fator_de_emissao_da_rede_kg_por_kwh'], 2)} "
                f"kg/kWh) é ilustrativo.")

    @staticmethod
    def _bateria(d, _):
        return (f"A bateria de {f(d['capacidade_da_bateria_kwh'], 0)} kWh começou o dia com {f(d['soc_no_inicio_do_dia_pct'], 0)}% "
                f"de carga, chegou a {f(d['soc_maximo_pct'], 0)}% às {d['hora_do_soc_maximo']} (excedente solar) e terminou "
                f"com {f(d['soc_no_fim_do_dia_pct'], 0)}%. Ela entregou {f(d['energia_entregue_pela_bateria_aos_veiculos_kwh'])} "
                f"kWh aos veículos.")
