"""
SolarCharge AI - simulacao integrada de um dia de operacao.

Como executar (na raiz do repositorio):
    python src/main.py

O que faz:
  1. Treina o modelo de IA (regressao) que preve a geracao solar e mede o erro em dias de teste.
  2. Simula 1 dia com 6 sessoes de recarga em DOIS cenarios:
        - baseline : solar + rede, carga imediata, sem bateria, sem IA
        - proposta : solar + bateria + agente inteligente com previsao solar
  3. Grava dados (CSV/JSON/JSONL) em data/ e graficos em docs/.
"""
import json

import numpy as np
import pandas as pd

from config import (
    SEED, C_DIA_DEMO, DT_H, DATA_DIR, DOCS_DIR, TARIFA_RS_KWH, FATOR_CO2_KG_KWH, PRECO_VENDA_RS_KWH, hhmm,
)
from pv import HORAS, gerar_nuvens, potencia_pv, treinar_e_avaliar
from station import simular_dia
import plots

# ---------------------------------------------------------------------
# Sessoes de recarga do dia (dados ficticios de veiculos)
# ---------------------------------------------------------------------
SESSOES_CFG = [
    dict(id=1, porta=1, veiculo="Hatch compacto 40 kWh",  cap_kwh=40, chegada_h=8.0,  saida_h=16.0, soc_ini=0.20, soc_alvo=0.90),
    dict(id=2, porta=2, veiculo="SUV eletrico 60 kWh",    cap_kwh=60, chegada_h=9.5,  saida_h=13.5, soc_ini=0.30, soc_alvo=0.65),
    dict(id=3, porta=3, veiculo="Sedan eletrico 50 kWh",  cap_kwh=50, chegada_h=11.0, saida_h=15.0, soc_ini=0.25, soc_alvo=0.70),
    dict(id=4, porta=2, veiculo="Hatch compacto 40 kWh",  cap_kwh=40, chegada_h=14.0, saida_h=18.5, soc_ini=0.35, soc_alvo=0.90),
    dict(id=5, porta=1, veiculo="Sedan eletrico 50 kWh",  cap_kwh=50, chegada_h=17.0, saida_h=22.0, soc_ini=0.20, soc_alvo=0.70),
    dict(id=6, porta=3, veiculo="Utilitario 35 kWh",      cap_kwh=35, chegada_h=18.5, saida_h=23.0, soc_ini=0.15, soc_alvo=0.65),
]


def calcular_metricas(linhas, sessoes, tem_bateria):
    df = pd.DataFrame(linhas)
    e = lambda col: float(df[col].sum() * DT_H)
    ev = e("ev_kw")
    solar, bat, rede = e("solar_para_ev_kw"), e("bateria_para_ev_kw"), e("rede_para_ev_kw")
    pv_total = e("pv_real_kw")
    m = {
        "energia_gerada_pv_kwh": round(pv_total, 1),
        "energia_entregue_aos_veiculos_kwh": round(ev, 1),
        "solar_direto_kwh": round(solar, 1),
        "bateria_kwh": round(bat, 1),
        "rede_kwh": round(rede, 1),
        "fracao_renovavel_pct": round(100 * (solar + bat) / ev, 1) if ev else 0,
        "pico_rede_kw": round(float(df["rede_para_ev_kw"].max()), 2),
        "excedente_solar_kwh": round(e("excedente_solar_kw"), 1),
        "receita_faturada_rs": round(ev * PRECO_VENDA_RS_KWH, 2),
        "custo_rede_rs": round(rede * TARIFA_RS_KWH, 2),
        "margem_rs": round(ev * PRECO_VENDA_RS_KWH - rede * TARIFA_RS_KWH, 2),
        "co2_rede_kg": round(rede * FATOR_CO2_KG_KWH, 2),
        "metas_atingidas": f"{sum(1 for s in sessoes if s.soc >= s.soc_alvo - 1e-3)}/{len(sessoes)}",
        "soc_final_bateria_pct": round(float(df['bateria_soc'].iloc[-1]) * 100, 1) if tem_bateria else None,
    }
    return m


def tabela_sessoes(sessoes, cenario):
    linhas = []
    for s in sessoes:
        renov = (s.kwh_solar + s.kwh_bateria) / s.kwh_total * 100 if s.kwh_total else 0
        linhas.append({
            "cenario": cenario, "sessao": s.id, "porta": s.porta, "veiculo": s.veiculo,
            "chegada": hhmm(s.chegada_h), "saida": hhmm(s.saida_h),
            "soc_inicial_pct": round(s.soc_ini * 100), "soc_alvo_pct": round(s.soc_alvo * 100),
            "soc_final_pct": round(s.soc * 100, 1),
            "meta_atingida": "sim" if s.soc >= s.soc_alvo - 1e-3 else "NAO",
            "inicio_carga": hhmm(s.inicio_carga_h) if s.inicio_carga_h is not None else "-",
            "fim_carga": hhmm(s.fim_carga_h) if s.fim_carga_h is not None else "-",
            "kwh_solar": round(s.kwh_solar, 2), "kwh_bateria": round(s.kwh_bateria, 2),
            "kwh_rede": round(s.kwh_rede, 2), "kwh_total": round(s.kwh_total, 2),
            "renovavel_pct": round(renov, 1),
            "faturamento_rs": round(s.kwh_total * PRECO_VENDA_RS_KWH, 2),
            "custo_rede_rs": round(s.kwh_rede * TARIFA_RS_KWH, 2),
            "margem_rs": round(s.kwh_total * PRECO_VENDA_RS_KWH - s.kwh_rede * TARIFA_RS_KWH, 2),
        })
    return linhas


def main():
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)

    # ---------- 1) IA: treino e avaliacao do previsor solar ----------
    rng_ia = np.random.default_rng(SEED + 1)
    previsor, met_ia = treinar_e_avaliar(rng_ia)
    print("Previsor solar (teste):", met_ia)

    # ---------- 2) dia simulado ----------
    rng_dia = np.random.default_rng(SEED)
    nuvens = gerar_nuvens(rng_dia, C_DIA_DEMO)
    pv_real = potencia_pv(HORAS, nuvens)
    nuvem_prevista = float(np.clip(C_DIA_DEMO + rng_dia.normal(0, 0.08), 0, 1))   # previsao do tempo (com erro)
    pv_prev = previsor.prever(HORAS, np.full_like(HORAS, nuvem_prevista))
    met_ia["nuvem_real_media_dia_demo"] = C_DIA_DEMO
    met_ia["nuvem_prevista_dia_demo"] = round(nuvem_prevista, 3)
    met_ia["erro_energia_dia_demo_pct"] = round(
        abs(pv_prev.sum() - pv_real.sum()) / pv_real.sum() * 100, 2)

    resultados = {}
    tabelas = []
    for modo in ("baseline", "proposta"):
        linhas, sessoes, bus = simular_dia(modo, SESSOES_CFG, pv_real, pv_prev, np.random.default_rng(SEED + 7))
        df = pd.DataFrame(linhas)
        df.to_csv(DATA_DIR / f"telemetria_{modo}.csv", index=False)
        bus.salvar_jsonl(DATA_DIR / f"mqtt_log_{modo}.jsonl")
        resultados[modo] = {
            "metricas": calcular_metricas(linhas, sessoes, tem_bateria=(modo == "proposta")),
            "df": df, "sessoes": sessoes, "bus": bus,
        }
        tabelas += tabela_sessoes(sessoes, modo)
        n_cmd = sum(1 for m in bus.log if m["topico"].endswith("/cmd") and "porta" in m["topico"])
        print(f"[{modo}] mensagens MQTT: {len(bus.log)} | comandos para carregadores: {n_cmd}")

    # ---------- 3) comparativo ----------
    b, p = resultados["baseline"]["metricas"], resultados["proposta"]["metricas"]
    comp = {
        "reducao_rede_pct": round(100 * (1 - p["rede_kwh"] / b["rede_kwh"]), 1),
        "reducao_pico_rede_pct": round(100 * (1 - p["pico_rede_kw"] / b["pico_rede_kw"]), 1),
        "economia_rs": round(b["custo_rede_rs"] - p["custo_rede_rs"], 2),
        "co2_evitado_kg": round(b["co2_rede_kg"] - p["co2_rede_kg"], 2),
        "ganho_fracao_renovavel_pontos": round(p["fracao_renovavel_pct"] - b["fracao_renovavel_pct"], 1),
    }
    saida = {"previsor_solar": met_ia, "baseline": b, "proposta": p, "comparativo": comp}
    with open(DATA_DIR / "metricas.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    pd.DataFrame(tabelas).to_csv(DATA_DIR / "sessoes.csv", index=False)

    # ---------- 4) graficos ----------
    plots.arquitetura(DOCS_DIR / "arquitetura.png")
    plots.painel_dia(resultados["proposta"], DOCS_DIR / "resultado_dia_proposta.png", "Proposta: solar + bateria + IA")
    plots.painel_dia(resultados["baseline"], DOCS_DIR / "resultado_dia_baseline.png", "Baseline: solar + rede (sem IA, sem bateria)")
    plots.comparativo(b, p, DOCS_DIR / "comparativo.png")
    plots.previsao(HORAS, pv_real, pv_prev, met_ia, DOCS_DIR / "previsao_solar.png")
    plots.fluxograma_chatbot(DOCS_DIR / "fluxograma_chatbot.png")

    print("\n=== METRICAS ===")
    print(json.dumps(saida, indent=2, ensure_ascii=False))
    print("\nArquivos gerados em data/ e docs/.")


if __name__ == "__main__":
    main()
