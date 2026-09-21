"""
Camada de dados do chatbot: le os arquivos gerados pela estacao (telemetria, sessoes, metricas)
e devolve FATOS estruturados. O LLM so pode falar o que estiver nesses fatos.
"""
import json

import pandas as pd

from config import DATA_DIR, BAT_CAP_KWH, REDE_LIMITE_KW, PRECO_VENDA_RS_KWH, TARIFA_RS_KWH, FATOR_CO2_KG_KWH


class DadosEstacao:
    def __init__(self, data_dir=DATA_DIR):
        try:
            with open(data_dir / "metricas.json", encoding="utf-8") as f:
                self.m = json.load(f)
            todas = pd.read_csv(data_dir / "sessoes.csv")
            self.sess = todas[todas.cenario == "proposta"].set_index("sessao")
            self.sess_base = todas[todas.cenario == "baseline"].set_index("sessao")
            self.tel = pd.read_csv(data_dir / "telemetria_proposta.csv")
        except FileNotFoundError as e:
            raise SystemExit("Dados nao encontrados. Rode primeiro:  python src/main.py") from e

    # ------------------------------------------------------------------ consultas
    def energia(self):
        p = self.m["proposta"]
        return {
            "energia_entregue_aos_veiculos_kwh": p["energia_entregue_aos_veiculos_kwh"],
            "energia_solar_direta_kwh": p["solar_direto_kwh"],
            "energia_da_bateria_kwh": p["bateria_kwh"],
            "energia_da_rede_kwh": p["rede_kwh"],
            "fracao_renovavel_pct": p["fracao_renovavel_pct"],
            "energia_gerada_pela_usina_solar_kwh": p["energia_gerada_pv_kwh"],
            "excedente_solar_nao_aproveitado_kwh": p["excedente_solar_kwh"],
        }

    def pico(self):
        t = self.tel
        linha = t.loc[t.rede_para_ev_kw.idxmax()]
        p, b = self.m["proposta"], self.m["baseline"]
        return {
            "pico_de_potencia_da_rede_kw": p["pico_rede_kw"],
            "hora_do_pico": linha["hora"],
            "pico_no_cenario_sem_ia_kw": b["pico_rede_kw"],
            "reducao_do_pico_pct": self.m["comparativo"]["reducao_pico_rede_pct"],
            "potencia_contratada_com_a_concessionaria_kw": REDE_LIMITE_KW,
        }

    def financeiro(self):
        p, b = self.m["proposta"], self.m["baseline"]
        return {
            "receita_faturada_rs": p["receita_faturada_rs"],
            "preco_de_venda_rs_por_kwh": PRECO_VENDA_RS_KWH,
            "custo_da_energia_da_rede_rs": p["custo_rede_rs"],
            "tarifa_da_rede_rs_por_kwh": TARIFA_RS_KWH,
            "margem_do_dia_rs": p["margem_rs"],
            "custo_da_rede_sem_ia_rs": b["custo_rede_rs"],
            "margem_sem_ia_rs": b["margem_rs"],
            "economia_do_dia_com_ia_rs": self.m["comparativo"]["economia_rs"],
            "observacao": "valores ficticios/ilustrativos de uma simulacao",
        }

    def previsao(self):
        q = self.m["previsor_solar"]
        return {
            "modelo": "regressao linear (aprendizado supervisionado)",
            "dias_de_treino": q["dias_treino"],
            "dias_de_teste_nunca_vistos": q["dias_teste"],
            "MAE_kw": q["MAE_kW"],
            "RMSE_kw": q["RMSE_kW"],
            "R2": q["R2"],
            "erro_medio_na_energia_diaria_pct": q["erro_medio_energia_diaria_pct"],
            "observacao": "treinado e testado com dados simulados",
        }

    def comparativo(self):
        p, b, c = self.m["proposta"], self.m["baseline"], self.m["comparativo"]
        return {
            "energia_da_rede_sem_ia_kwh": b["rede_kwh"],
            "energia_da_rede_com_ia_kwh": p["rede_kwh"],
            "reducao_da_energia_da_rede_pct": c["reducao_rede_pct"],
            "fracao_renovavel_sem_ia_pct": b["fracao_renovavel_pct"],
            "fracao_renovavel_com_ia_pct": p["fracao_renovavel_pct"],
            "ganho_de_fracao_renovavel_pontos_percentuais": c["ganho_fracao_renovavel_pontos"],
            "pico_da_rede_sem_ia_kw": b["pico_rede_kw"],
            "pico_da_rede_com_ia_kw": p["pico_rede_kw"],
            "reducao_do_pico_pct": c["reducao_pico_rede_pct"],
            "economia_no_custo_da_rede_rs": c["economia_rs"],
            "co2_evitado_kg": c["co2_evitado_kg"],
            "metas_de_carga_atingidas_com_ia": p["metas_atingidas"],
        }

    def sustentabilidade(self):
        p, b, c = self.m["proposta"], self.m["baseline"], self.m["comparativo"]
        return {
            "co2_da_rede_com_ia_kg": p["co2_rede_kg"],
            "co2_da_rede_sem_ia_kg": b["co2_rede_kg"],
            "co2_evitado_kg": c["co2_evitado_kg"],
            "fracao_renovavel_pct": p["fracao_renovavel_pct"],
            "fator_de_emissao_da_rede_kg_por_kwh": FATOR_CO2_KG_KWH,
            "observacao": "fator de emissao ilustrativo",
        }

    def bateria(self):
        t = self.tel
        soc = t["bateria_soc"].astype(float)
        return {
            "capacidade_da_bateria_kwh": BAT_CAP_KWH,
            "soc_no_inicio_do_dia_pct": round(soc.iloc[0] * 100, 1),
            "soc_maximo_pct": round(soc.max() * 100, 1),
            "hora_do_soc_maximo": t.loc[soc.idxmax(), "hora"],
            "soc_no_fim_do_dia_pct": round(soc.iloc[-1] * 100, 1),
            "energia_entregue_pela_bateria_aos_veiculos_kwh": self.m["proposta"]["bateria_kwh"],
        }

    def status_em(self, hh: int, mm: int):
        mm = int(round(mm / 5.0) * 5)
        if mm == 60:
            hh, mm = hh + 1, 0
        rotulo = f"{hh % 24:02d}:{mm:02d}"
        linha = self.tel[self.tel.hora == rotulo]
        if linha.empty:
            return None
        r = linha.iloc[0]
        return {
            "hora": rotulo,
            "veiculos_conectados": int(r["veiculos_conectados"]),
            "potencia_total_para_veiculos_kw": r["ev_kw"],
            "solar_para_veiculos_kw": r["solar_para_ev_kw"],
            "bateria_para_veiculos_kw": r["bateria_para_ev_kw"],
            "rede_para_veiculos_kw": r["rede_para_ev_kw"],
            "geracao_solar_kw": r["pv_real_kw"],
            "soc_da_bateria_pct": round(float(r["bateria_soc"]) * 100, 1),
        }

    def n_sessoes(self):
        return int(len(self.sess))

    def sessao(self, n: int):
        if n not in self.sess.index:
            return None
        r = self.sess.loc[n]
        rb = self.sess_base.loc[n]
        return {
            "sessao": n,
            "porta": int(r["porta"]),
            "veiculo": r["veiculo"],
            "chegada": r["chegada"],
            "saida": r["saida"],
            "soc_inicial_pct": int(r["soc_inicial_pct"]),
            "soc_final_pct": float(r["soc_final_pct"]),
            "soc_alvo_pct": int(r["soc_alvo_pct"]),
            "meta_atingida": r["meta_atingida"],
            "inicio_da_carga": r["inicio_carga"],
            "fim_da_carga": r["fim_carga"],
            "energia_solar_kwh": float(r["kwh_solar"]),
            "energia_da_bateria_kwh": float(r["kwh_bateria"]),
            "energia_da_rede_kwh": float(r["kwh_rede"]),
            "energia_total_kwh": float(r["kwh_total"]),
            "renovavel_pct": float(r["renovavel_pct"]),
            "faturamento_rs": float(r["faturamento_rs"]),
            "custo_da_rede_rs": float(r["custo_rede_rs"]),
            "energia_da_rede_sem_ia_kwh": float(rb["kwh_rede"]),
            "explicacao": self._explicar(r),
        }

    def lista_sessoes(self):
        fatos = {"total_de_sessoes": self.n_sessoes()}
        for n, r in self.sess.iterrows():
            fatos[f"sessao_{n}"] = (
                f"porta {int(r['porta'])}, {r['chegada']}-{r['saida']}, SoC {int(r['soc_inicial_pct'])}% -> "
                f"{r['soc_final_pct']:g}% (meta {int(r['soc_alvo_pct'])}%, atingida: {r['meta_atingida']}), "
                f"solar {r['kwh_solar']:g} kWh, bateria {r['kwh_bateria']:g} kWh, rede {r['kwh_rede']:g} kWh, "
                f"faturamento R$ {r['faturamento_rs']:g}"
            )
        return fatos

    @staticmethod
    def _explicar(r) -> str:
        chegada_h = int(str(r["chegada"]).split(":")[0])
        if r["renovavel_pct"] >= 95:
            return ("Recarga feita quase só com solar direto, porque o veículo ficou conectado durante o período "
                    "de sol e o gerenciador priorizou a geração solar.")
        if r["kwh_solar"] < 2 and chegada_h >= 17:
            return ("Sessão no período noturno, sem geração solar. O gerenciador usou a bateria primeiro e a rede "
                    "só para completar o déficit e cumprir a meta até a hora de saída.")
        return ("Sessão mista: começou com solar, mas a geração caiu no fim da tarde; o gerenciador complementou "
                "com bateria e rede apenas o necessário para cumprir a meta até a saída.")

    # ------------------------------------------------------------------ despacho
    def consultar(self, intent: str, params: dict):
        """Devolve (fatos: dict | None). None = nao ha dado para o pedido."""
        if intent == "sessao":
            return self.sessao(params["n"])
        if intent == "status":
            return self.status_em(params["hh"], params["mm"])
        if intent in ("energia", "pico", "financeiro", "previsao", "comparativo",
                      "sustentabilidade", "bateria", "lista_sessoes"):
            return getattr(self, intent)()
        return {}
