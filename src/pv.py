"""
Geracao solar simulada + modelo de IA (regressao linear) para previsao da geracao.

- ceu_limpo(): formato da curva solar ao longo do dia (nasce ~6h, poe ~18h).
- gerar_nuvens(): cobertura de nuvens minuto a minuto (passeio aleatorio suave).
- potencia_pv(): potencia real gerada pela usina.
- PrevisorSolar: aprendizado supervisionado (minimos quadrados) que aprende, com dias
  historicos, a prever a potencia FV a partir da hora do dia e da previsao de nuvens.
"""
import numpy as np

from config import DT_H, PASSOS, PV_KWP, PV_DESEMPENHO

HORAS = np.arange(PASSOS) * DT_H


def ceu_limpo(horas: np.ndarray) -> np.ndarray:
    """Fator 0..1 da irradiacao em ceu limpo (meio-seno entre 6h e 18h)."""
    x = np.clip((horas - 6.0) / 12.0, 0.0, 1.0)
    return np.where((horas >= 6.0) & (horas <= 18.0), np.sin(np.pi * x) ** 1.3, 0.0)


def gerar_nuvens(rng: np.random.Generator, c_dia: float) -> np.ndarray:
    """Cobertura de nuvens (0..1) a cada 5 min, variando em torno da media do dia."""
    ruido = np.zeros(PASSOS)
    for i in range(1, PASSOS):
        ruido[i] = 0.97 * ruido[i - 1] + rng.normal(0.0, 0.04)
    return np.clip(c_dia + ruido, 0.0, 1.0)


def potencia_pv(horas: np.ndarray, nuvens: np.ndarray) -> np.ndarray:
    """Potencia real (kW) da usina solar."""
    return PV_KWP * PV_DESEMPENHO * ceu_limpo(horas) * (1.0 - 0.75 * nuvens)


class PrevisorSolar:
    """Regressao linear: pv_previsto = a*cs + b*cs*nuvem + c*cs*nuvem^2  (cs = ceu limpo)."""

    def __init__(self):
        self.pesos = None

    @staticmethod
    def _atributos(horas, nuvem_prevista):
        cs = ceu_limpo(horas)
        return np.column_stack([cs, cs * nuvem_prevista, cs * nuvem_prevista ** 2])

    def treinar(self, horas, nuvem_prevista, pv_medida):
        X = self._atributos(horas, nuvem_prevista)
        self.pesos, *_ = np.linalg.lstsq(X, pv_medida, rcond=None)

    def prever(self, horas, nuvem_prevista) -> np.ndarray:
        return np.clip(self._atributos(horas, nuvem_prevista) @ self.pesos, 0.0, None)


def gerar_historico(rng: np.random.Generator, n_dias: int):
    """Cria n_dias de historico: horas, previsao de nuvens (com erro) e potencia medida (com ruido)."""
    H, NP, PV = [], [], []
    for _ in range(n_dias):
        c_dia = rng.uniform(0.05, 0.85)
        nuvens = gerar_nuvens(rng, c_dia)
        pv = potencia_pv(HORAS, nuvens) * (1 + rng.normal(0, 0.02, PASSOS))
        nuvem_prevista = np.clip(c_dia + rng.normal(0, 0.08), 0, 1)   # previsao do tempo com erro
        H.append(HORAS)
        NP.append(np.full(PASSOS, nuvem_prevista))
        PV.append(np.clip(pv, 0, None))
    return np.concatenate(H), np.concatenate(NP), np.concatenate(PV)


def treinar_e_avaliar(rng: np.random.Generator, n_treino=120, n_teste=30):
    """Treina o modelo e devolve (modelo, metricas no conjunto de teste)."""
    h_tr, n_tr, pv_tr = gerar_historico(rng, n_treino)
    h_te, n_te, pv_te = gerar_historico(rng, n_teste)
    modelo = PrevisorSolar()
    modelo.treinar(h_tr, n_tr, pv_tr)
    pred = modelo.prever(h_te, n_te)
    erro = pred - pv_te
    mae = float(np.mean(np.abs(erro)))
    rmse = float(np.sqrt(np.mean(erro ** 2)))
    r2 = float(1 - np.sum(erro ** 2) / np.sum((pv_te - pv_te.mean()) ** 2))
    # erro na energia diaria
    e_real = pv_te.reshape(n_teste, PASSOS).sum(axis=1) * DT_H
    e_prev = pred.reshape(n_teste, PASSOS).sum(axis=1) * DT_H
    erro_energia_pct = float(np.mean(np.abs(e_prev - e_real) / e_real) * 100)
    metricas = {
        "dias_treino": n_treino,
        "dias_teste": n_teste,
        "MAE_kW": round(mae, 3),
        "RMSE_kW": round(rmse, 3),
        "R2": round(r2, 4),
        "erro_medio_energia_diaria_pct": round(erro_energia_pct, 2),
        "pesos_modelo": [round(float(w), 4) for w in modelo.pesos],
    }
    return modelo, metricas
