"""
Parametros da simulacao da estacao SolarCharge AI.
Todos os valores podem ser alterados aqui sem mexer no resto do codigo.
"""
from pathlib import Path

# ---------- pastas ----------
RAIZ = Path(__file__).resolve().parents[1]
DATA_DIR = RAIZ / "data"
DOCS_DIR = RAIZ / "docs"

# ---------- tempo ----------
DT_H = 5 / 60            # passo de 5 minutos, em horas
PASSOS = 288             # 24 h / 5 min
SEED = 42                # semente aleatoria (resultados reproduziveis)

# ---------- usina solar ----------
PV_KWP = 30.0            # potencia de pico instalada (kWp)
PV_DESEMPENHO = 0.80     # performance ratio (perdas do sistema)
C_DIA_DEMO = 0.35        # cobertura media de nuvens do dia simulado (0=ceu limpo, 1=encoberto)

# ---------- bateria estacionaria ----------
BAT_CAP_KWH = 20.0
BAT_MAX_KW = 10.0
BAT_SOC_MIN = 0.20
BAT_SOC_MAX = 0.90
BAT_SOC_INI = 0.20   # comeca no minimo: toda energia da bateria vem do sol DO PROPRIO DIA
BAT_ETA = 0.95           # eficiencia em cada sentido (carga e descarga)

# ---------- estacao de recarga ----------
N_PORTAS = 4
PORTA_MAX_KW = 7.4       # carregador AC monofasico (32 A x 230 V)
CARGA_ETA = 0.92         # eficiencia carregador + bateria do veiculo
REDE_LIMITE_KW = 22.0    # limite de potencia contratada com a concessionaria

# ---------- economia e ambiente (VALORES ILUSTRATIVOS - ajuste se quiser) ----------
TARIFA_RS_KWH = 0.95         # R$/kWh da rede
FATOR_CO2_KG_KWH = 0.06      # kg CO2/kWh da rede (media anual aproximada do SIN; confira o valor oficial)
PRECO_VENDA_RS_KWH = 2.20    # R$/kWh cobrado do motorista (faturamento da estacao) - valor ficticio

# ---------- controlador inteligente ----------
CONFIANCA_SOLAR = 0.80   # quanto da previsao solar o agente "confia" ao planejar
FOLGA_CRITICA = 0.85     # sessao e "critica" se precisar de >85% da potencia maxima ate a saida


def hhmm(horas: float) -> str:
    """Converte hora decimal (ex.: 8.5) em texto 'HH:MM'."""
    minutos = int(round(horas * 60))
    return f"{(minutos // 60) % 24:02d}:{minutos % 60:02d}"
