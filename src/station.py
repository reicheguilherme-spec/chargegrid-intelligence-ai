"""
Componentes da estacao de recarga e controladores.

Fluxo de integracao (tudo conversa pelo barramento MQTT):

  SensorPV / Bateria(BMS) / Carregadores --(telemetria)--> Controlador
  Controlador --(comandos START / SET_POWER / STOP)--> Carregadores e Bateria

Dois controladores sao comparados:
  * ControladorBaseline    : carrega imediatamente na potencia maxima (solar primeiro, resto da rede).
  * ControladorInteligente : agente com previsao solar (IA) + bateria + carga "so o necessario da rede".
"""
import numpy as np

from bus import BarramentoMQTT
from config import (
    DT_H, PASSOS, N_PORTAS, PORTA_MAX_KW, CARGA_ETA, REDE_LIMITE_KW,
    BAT_CAP_KWH, BAT_MAX_KW, BAT_SOC_MIN, BAT_SOC_MAX, BAT_SOC_INI, BAT_ETA,
    CONFIANCA_SOLAR, FOLGA_CRITICA, hhmm,
)

ZERO = {"solar": 0.0, "bateria": 0.0, "rede": 0.0}


# =====================================================================
# Sessao de recarga (dados do veiculo + contabilidade de energia)
# =====================================================================
class Sessao:
    def __init__(self, id, porta, veiculo, cap_kwh, chegada_h, saida_h, soc_ini, soc_alvo):
        self.id, self.porta, self.veiculo = id, porta, veiculo
        self.cap_kwh, self.chegada_h, self.saida_h = cap_kwh, chegada_h, saida_h
        self.soc_ini, self.soc_alvo = soc_ini, soc_alvo
        self.soc = soc_ini
        self.estado = "AGENDADA"
        self.kwh_solar = self.kwh_bateria = self.kwh_rede = 0.0
        self.inicio_carga_h = None
        self.fim_carga_h = None
        self.hist = []          # lista de (hora, soc)

    def falta_kwh(self) -> float:
        """Energia que a estacao ainda precisa entregar (ja considerando perdas)."""
        return max(0.0, (self.soc_alvo - self.soc) * self.cap_kwh / CARGA_ETA)

    @property
    def kwh_total(self) -> float:
        return self.kwh_solar + self.kwh_bateria + self.kwh_rede


# =====================================================================
# Dispositivos "fisicos" (simulados)
# =====================================================================
class SensorPV:
    """Sensor de tensao/corrente do inversor: mede a potencia FV com 2% de ruido."""

    def __init__(self, bus, rng):
        self.bus, self.rng = bus, rng

    def amostrar(self, pv_real_kw: float):
        medida = max(0.0, pv_real_kw * (1 + self.rng.normal(0, 0.02)))
        self.bus.publicar("estacao/pv/potencia", {"kw": round(medida, 3)})


class Bateria:
    """Bateria estacionaria com BMS (limites de SoC e de potencia)."""

    def __init__(self, bus, ativa=True):
        self.bus, self.ativa = bus, ativa
        self.soc = BAT_SOC_INI if ativa else 0.0
        self.cmd_carga_kw = 0.0
        bus.assinar("estacao/bateria/cmd", self._ao_receber_comando)

    def max_descarga_kw(self) -> float:
        if not self.ativa:
            return 0.0
        energia = max(0.0, (self.soc - BAT_SOC_MIN) * BAT_CAP_KWH)
        return min(BAT_MAX_KW, energia * BAT_ETA / DT_H)

    def max_carga_kw(self) -> float:
        if not self.ativa:
            return 0.0
        folga = max(0.0, (BAT_SOC_MAX - self.soc) * BAT_CAP_KWH)
        return min(BAT_MAX_KW, folga / (BAT_ETA * DT_H))

    def _ao_receber_comando(self, topico, p):
        self.cmd_carga_kw = p.get("carga_kw", 0.0)

    def aplicar(self, carga_kw, descarga_kw):
        if self.ativa:
            self.soc += (carga_kw * DT_H * BAT_ETA - descarga_kw * DT_H / BAT_ETA) / BAT_CAP_KWH

    def reportar(self):
        self.bus.publicar("estacao/bateria/estado", {
            "soc": round(self.soc, 4),
            "max_descarga_kw": round(self.max_descarga_kw(), 3),
            "max_carga_kw": round(self.max_carga_kw(), 3),
        })


class Carregador:
    """Ponto de recarga (EVSE): recebe comandos, aciona o contator e mede a energia entregue."""

    def __init__(self, porta, bus):
        self.porta, self.bus = porta, bus
        self.sessao = None
        self.contator = False
        self.kw_set = 0.0
        self.fontes = dict(ZERO)
        self.kw_entregue = 0.0
        bus.assinar(f"estacao/porta/{porta}/cmd", self._ao_receber_comando)

    # ---- eventos de conexao ----
    def conectar(self, s: Sessao):
        self.sessao = s
        s.estado = "CONECTADA"
        self.bus.publicar(f"estacao/porta/{self.porta}/evento", {
            "evento": "VEICULO_CONECTADO", "veiculo": s.veiculo, "cap_kwh": s.cap_kwh,
            "soc": round(s.soc, 4), "soc_alvo": s.soc_alvo, "saida_h": s.saida_h,
        })

    def desconectar(self):
        s = self.sessao
        s.estado = "FINALIZADA"
        self.bus.publicar(f"estacao/porta/{self.porta}/evento", {
            "evento": "VEICULO_DESCONECTADO", "soc_final": round(s.soc, 4),
        })
        self.sessao, self.contator, self.kw_set, self.fontes, self.kw_entregue = None, False, 0.0, dict(ZERO), 0.0

    # ---- comandos recebidos do controlador ----
    def _ao_receber_comando(self, topico, p):
        cmd = p["cmd"]
        if cmd in ("START", "SET_POWER"):
            self.contator, self.kw_set, self.fontes = True, p["kw"], p["fontes"]
        elif cmd == "STOP":
            self.contator, self.kw_set, self.fontes = False, 0.0, dict(ZERO)

    # ---- fisica ----
    def calcular(self):
        """Potencia efetiva neste passo e como ela se divide entre as fontes."""
        s = self.sessao
        if s is None or not self.contator:
            return 0.0, 0.0, 0.0, 0.0
        kw = min(self.kw_set, PORTA_MAX_KW, s.falta_kwh() / DT_H)
        total = sum(self.fontes.values())
        if kw <= 1e-9 or total <= 1e-9:
            return 0.0, 0.0, 0.0, 0.0
        sol = kw * self.fontes["solar"] / total
        bat = kw * self.fontes["bateria"] / total
        return kw, sol, bat, kw - sol - bat

    def aplicar(self, t_h, kw, sol, bat, rede):
        s = self.sessao
        self.kw_entregue = kw
        if s is None:
            return
        if kw > 0:
            if s.inicio_carga_h is None:
                s.inicio_carga_h = t_h
            s.estado = "CARREGANDO"
            s.soc += kw * DT_H * CARGA_ETA / s.cap_kwh
            s.kwh_solar += sol * DT_H
            s.kwh_bateria += bat * DT_H
            s.kwh_rede += rede * DT_H
        if s.soc >= s.soc_alvo - 1e-4 and s.fim_carga_h is None:
            s.soc = min(s.soc, s.soc_alvo)
            s.fim_carga_h = t_h + DT_H
            s.estado = "CONCLUIDA"
        s.hist.append((t_h + DT_H, s.soc))

    def reportar(self):
        s = self.sessao
        if s is None:
            return
        self.bus.publicar(f"estacao/porta/{self.porta}/medicao", {
            "kw": round(self.kw_entregue, 3), "soc": round(s.soc, 4), "kwh": round(s.kwh_total, 3),
        })


# =====================================================================
# Controladores
# =====================================================================
class ControladorBase:
    """Recebe telemetria pelo barramento e publica comandos. Subclasses implementam decidir()."""

    def __init__(self, bus: BarramentoMQTT):
        self.bus = bus
        self.pv_kw = 0.0
        self.bat = {"soc": 0.0, "max_descarga_kw": 0.0, "max_carga_kw": 0.0}
        self.portas = {}          # porta -> dados do veiculo conectado
        self.ultimo = {}          # porta -> (kw, fontes) do ultimo comando
        bus.assinar("estacao/pv/potencia", lambda t, p: setattr(self, "pv_kw", p["kw"]))
        bus.assinar("estacao/bateria/estado", lambda t, p: setattr(self, "bat", p))
        bus.assinar("estacao/porta/+/evento", self._ao_receber_evento)
        bus.assinar("estacao/porta/+/medicao", self._ao_receber_medicao)

    @staticmethod
    def _porta(topico):
        return int(topico.split("/")[2])

    def _ao_receber_evento(self, topico, p):
        porta = self._porta(topico)
        if p["evento"] == "VEICULO_CONECTADO":
            self.portas[porta] = {k: p[k] for k in ("cap_kwh", "soc", "soc_alvo", "saida_h")}
        else:
            self.portas.pop(porta, None)
            self.ultimo.pop(porta, None)

    def _ao_receber_medicao(self, topico, p):
        porta = self._porta(topico)
        if porta in self.portas:
            self.portas[porta]["soc"] = p["soc"]

    def _enviar(self, porta, kw, fontes):
        """Publica comando somente quando algo mudou (evita mensagens repetidas)."""
        kw_ant, fontes_ant = self.ultimo.get(porta, (0.0, ZERO))
        if abs(kw - kw_ant) < 0.05 and all(abs(fontes[k] - fontes_ant[k]) < 0.05 for k in ZERO):
            return
        cmd = "START" if kw_ant <= 0 < kw else ("STOP" if kw <= 0 < kw_ant else "SET_POWER")
        if kw <= 0 and kw_ant <= 0:
            return
        self.ultimo[porta] = (kw, dict(fontes))
        self.bus.publicar(f"estacao/porta/{porta}/cmd", {
            "cmd": cmd, "kw": round(kw, 3), "fontes": {k: round(v, 3) for k, v in fontes.items()},
        })

    def _falta(self, d):
        return max(0.0, (d["soc_alvo"] - d["soc"]) * d["cap_kwh"] / CARGA_ETA)

    def decidir(self, t_h, k):
        raise NotImplementedError


class ControladorBaseline(ControladorBase):
    """Sem IA e sem bateria: carrega ja, na potencia maxima. Usa o sol que tiver; o resto vem da rede."""

    def decidir(self, t_h, k):
        solar_livre, rede_livre = self.pv_kw, REDE_LIMITE_KW
        for porta in sorted(self.portas):
            falta = self._falta(self.portas[porta])
            if falta <= 1e-6:
                self._enviar(porta, 0.0, ZERO)
                continue
            alvo = min(PORTA_MAX_KW, falta / DT_H)
            sol = min(alvo, solar_livre)
            solar_livre -= sol
            rede = min(alvo - sol, rede_livre)
            rede_livre -= rede
            self._enviar(porta, sol + rede, {"solar": sol, "bateria": 0.0, "rede": rede})
        self.bus.publicar("estacao/bateria/cmd", {"carga_kw": 0.0, "descarga_kw": 0.0})


class ControladorInteligente(ControladorBase):
    """
    Agente inteligente baseado em objetivos/utilidade.
    Objetivo: entregar a meta de SoC de cada veiculo ate a hora de saida usando o MINIMO de rede.

    A cada 5 min, para cada veiculo conectado:
      1. falta   = energia que ainda precisa entregar
      2. solar_prev = energia solar PREVISTA (IA) ate a saida, dividida entre os veiculos ativos
      3. deficit = parte da falta que a previsao solar NAO cobre  -> so isso pode vir da rede/bateria
      4. critica = se o tempo restante esta apertado -> libera potencia maxima (garante a meta)
    Prioridade das fontes:  solar > bateria (so quando nao ha sol ou caso critico) > rede (limitada ao deficit).
    O excedente solar carrega a bateria estacionaria.
    """

    def __init__(self, bus, pv_prevista_kw):
        super().__init__(bus)
        self.pv_prev = np.asarray(pv_prevista_kw)
        self.carga_bat_kw = 0.0

    def decidir(self, t_h, k):
        ativas = {p: d for p, d in self.portas.items() if self._falta(d) > 1e-4 * d["cap_kwh"]}
        for p in self.portas:
            if p not in ativas:
                self._enviar(p, 0.0, ZERO)

        n = max(len(ativas), 1)
        planos = {}
        for p, d in ativas.items():
            falta = self._falta(d)
            rest = max(d["saida_h"] - t_h, DT_H)
            k1 = min(int(round(d["saida_h"] / DT_H)), PASSOS)
            solar_prev = float(np.sum(self.pv_prev[k:k1])) * DT_H / n
            deficit = max(0.0, falta - CONFIANCA_SOLAR * solar_prev)
            planos[p] = {
                "falta": falta, "rest": rest, "deficit": deficit,
                "p_def": deficit / rest,
                "critica": falta >= FOLGA_CRITICA * PORTA_MAX_KW * rest,
                "urg": falta / (PORTA_MAX_KW * rest),
            }

        solar_livre = self.pv_kw
        bat_livre = self.bat["max_descarga_kw"]
        rede_livre = REDE_LIMITE_KW
        total_bat = total_sol = total_rede = 0.0

        for p in sorted(planos, key=lambda x: -planos[x]["urg"]):     # mais urgente primeiro
            pl = planos[p]
            alvo = min(PORTA_MAX_KW, pl["falta"] / DT_H)
            sol = min(alvo, solar_livre)
            solar_livre -= sol
            resto = alvo - sol

            bat = 0.0
            if resto > 1e-9 and (pl["critica"] or (pl["deficit"] > 0 and self.pv_kw < 1.0)):
                bat = min(resto, bat_livre)
                bat_livre -= bat
                resto -= bat

            rede = 0.0
            if resto > 1e-9:
                teto = PORTA_MAX_KW if pl["critica"] else min(PORTA_MAX_KW, 1.15 * pl["p_def"])
                rede = min(resto, teto, rede_livre)
                rede_livre -= rede

            self._enviar(p, sol + bat + rede, {"solar": sol, "bateria": bat, "rede": rede})
            total_sol += sol
            total_bat += bat
            total_rede += rede

        carga_bat = min(max(solar_livre, 0.0), self.bat["max_carga_kw"])
        self.carga_bat_kw = carga_bat
        self.bus.publicar("estacao/bateria/cmd", {"carga_kw": round(carga_bat, 3), "descarga_kw": round(total_bat, 3)})
        self.bus.publicar("estacao/despacho", {
            "solar_kw": round(total_sol, 3), "bateria_kw": round(total_bat, 3),
            "rede_kw": round(total_rede, 3), "carga_bateria_kw": round(carga_bat, 3),
        })


# =====================================================================
# Simulador do dia
# =====================================================================
def simular_dia(modo, sessoes_cfg, pv_real, pv_prevista, rng):
    """
    modo: 'baseline' ou 'proposta'.
    Devolve (linhas_de_telemetria, sessoes, bus).
    """
    bus = BarramentoMQTT()
    sessoes = [Sessao(**c) for c in sessoes_cfg]
    carregadores = {p: Carregador(p, bus) for p in range(1, N_PORTAS + 1)}
    bateria = Bateria(bus, ativa=(modo == "proposta"))
    sensor = SensorPV(bus, rng)
    if modo == "proposta":
        ctrl = ControladorInteligente(bus, pv_prevista)
        bus.publicar("estacao/ia/previsao_solar", {"kw_5min": [round(float(x), 2) for x in pv_prevista]})
    else:
        ctrl = ControladorBaseline(bus)

    linhas = []
    for k in range(PASSOS):
        t = k * DT_H
        bus.agora_h = t

        # 1) chegadas e saidas de veiculos
        for s in sessoes:
            if s.estado == "AGENDADA" and t >= s.chegada_h - 1e-9:
                carregadores[s.porta].conectar(s)
            elif s.estado in ("CONECTADA", "CARREGANDO", "CONCLUIDA") and t >= s.saida_h - 1e-9:
                carregadores[s.porta].desconectar()

        # 2) sensores e dispositivos publicam telemetria
        sensor.amostrar(pv_real[k])
        bateria.reportar()
        for ch in carregadores.values():
            ch.reportar()

        # 3) controlador decide e publica comandos
        ctrl.decidir(t, k)

        # 4) fisica: balanco de potencia do passo
        calc = [(ch,) + ch.calcular() for ch in carregadores.values()]
        solar_pedida = sum(c[2] for c in calc)
        fator = 1.0 if solar_pedida <= pv_real[k] or solar_pedida == 0 else pv_real[k] / solar_pedida
        ev_kw = solar_kw = bat_kw = rede_kw = 0.0
        for ch, kw, sol, bat, rede in calc:
            sol_r = sol * fator
            rede_r = rede + (sol - sol_r)          # se o sensor superestimou o sol, a rede cobre a diferenca
            ch.aplicar(t, kw, sol_r, bat, rede_r)
            ev_kw += kw
            solar_kw += sol_r
            bat_kw += bat
            rede_kw += rede_r

        sobra_solar = max(0.0, pv_real[k] - solar_kw)
        carga_bat = min(bateria.cmd_carga_kw, sobra_solar, bateria.max_carga_kw())
        bateria.aplicar(carga_bat, bat_kw)
        excedente = max(0.0, sobra_solar - carga_bat)

        linhas.append({
            "hora": hhmm(t),
            "hora_dec": round(t, 4),
            "pv_real_kw": round(float(pv_real[k]), 3),
            "pv_previsto_kw": round(float(pv_prevista[k]), 3) if modo == "proposta" else "",
            "ev_kw": round(ev_kw, 3),
            "solar_para_ev_kw": round(solar_kw, 3),
            "bateria_para_ev_kw": round(bat_kw, 3),
            "rede_para_ev_kw": round(rede_kw, 3),
            "carga_bateria_kw": round(carga_bat, 3),
            "bateria_soc": round(bateria.soc, 4) if bateria.ativa else "",
            "excedente_solar_kw": round(excedente, 3),
            "veiculos_conectados": sum(1 for s in sessoes if s.estado in ("CONECTADA", "CARREGANDO", "CONCLUIDA")),
        })

    return linhas, sessoes, bus
