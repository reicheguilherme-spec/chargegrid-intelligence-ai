"""Graficos e diagrama de arquitetura (gerados automaticamente pelo main.py)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

COR_SOLAR = "#F5A623"
COR_BAT = "#2E9E6B"
COR_REDE = "#5B6B8C"
COR_TXT = "#1f2933"


# ---------------------------------------------------------------------
def painel_dia(res, caminho, titulo):
    df, sessoes = res["df"], res["sessoes"]
    t = df["hora_dec"]
    tem_bat = df["bateria_soc"].iloc[0] != ""
    nlin = 3 if tem_bat else 2
    fig, axs = plt.subplots(nlin, 1, figsize=(12, 3.4 * nlin), sharex=True)

    ax = axs[0]
    ax.stackplot(t, df["solar_para_ev_kw"], df["bateria_para_ev_kw"], df["rede_para_ev_kw"],
                 labels=["Solar → veículos", "Bateria → veículos", "Rede → veículos"],
                 colors=[COR_SOLAR, COR_BAT, COR_REDE], alpha=0.9, step="post")
    ax.plot(t, df["pv_real_kw"], color="black", lw=1.4, label="Geração solar real")
    if df["pv_previsto_kw"].iloc[0] != "":
        ax.plot(t, df["pv_previsto_kw"].astype(float), color="black", lw=1.2, ls="--", label="Previsão da IA")
    ax.set_ylabel("Potência (kW)")
    ax.set_title(titulo, fontsize=13, fontweight="bold", color=COR_TXT)
    ax.legend(loc="upper left", ncol=3, fontsize=8.5, frameon=False)
    ax.grid(alpha=0.25)

    ax = axs[1]
    for s in sessoes:
        xs = [s.chegada_h] + [h for h, _ in s.hist]
        ys = [s.soc_ini * 100] + [v * 100 for _, v in s.hist]
        (linha,) = ax.plot(xs, ys, lw=2, label=f"Sessão {s.id} (porta {s.porta})")
        ax.hlines(s.soc_alvo * 100, s.chegada_h, s.saida_h, colors=linha.get_color(), linestyles=":", lw=1)
    ax.set_ylabel("SoC do veículo (%)")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper left", ncol=3, fontsize=8.5, frameon=False)
    ax.grid(alpha=0.25)
    ax.text(0.995, 0.04, "linha pontilhada = meta de carga", transform=ax.transAxes,
            ha="right", fontsize=8, color="#555")

    if tem_bat:
        ax = axs[2]
        ax.plot(t, df["bateria_soc"].astype(float) * 100, color=COR_BAT, lw=2)
        ax.fill_between(t, df["bateria_soc"].astype(float) * 100, color=COR_BAT, alpha=0.2)
        ax.set_ylabel("SoC bateria estacionária (%)")
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.25)

    axs[-1].set_xlabel("Hora do dia")
    axs[-1].set_xticks(range(0, 25, 2))
    axs[-1].set_xlim(0, 24)
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------------
def comparativo(b, p, caminho):
    itens = [
        ("Energia da rede (kWh)", "rede_kwh"),
        ("Fração renovável (%)", "fracao_renovavel_pct"),
        ("Pico de potência da rede (kW)", "pico_rede_kw"),
        ("CO₂ da rede (kg)", "co2_rede_kg"),
    ]
    fig, axs = plt.subplots(1, 4, figsize=(14, 3.8))
    for ax, (nome, chave) in zip(axs, itens):
        vals = [b[chave], p[chave]]
        barras = ax.bar(["Baseline", "Proposta"], vals, color=["#9aa5b1", COR_BAT], width=0.6)
        for r, v in zip(barras, vals):
            ax.text(r.get_x() + r.get_width() / 2, v, f"{v:g}", ha="center", va="bottom", fontsize=10, fontweight="bold")
        ax.set_title(nome, fontsize=10.5)
        ax.set_ylim(0, max(vals) * 1.2 if max(vals) else 1)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Baseline (sem IA, sem bateria) × Proposta (IA + bateria) — mesmo dia, mesmas 6 sessões",
                 fontsize=12, fontweight="bold", color=COR_TXT)
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------------
def previsao(horas, pv_real, pv_prev, met, caminho):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(horas, pv_real, color=COR_SOLAR, alpha=0.4, label="Geração real (com nuvens)")
    ax.plot(horas, pv_real, color=COR_SOLAR, lw=1.2)
    ax.plot(horas, pv_prev, color="black", ls="--", lw=1.6, label="Previsão do modelo de IA")
    ax.set_xlabel("Hora do dia")
    ax.set_ylabel("Potência FV (kW)")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, loc="upper left")
    txt = (f"Teste em {met['dias_teste']} dias inéditos\n"
           f"MAE = {met['MAE_kW']} kW\nRMSE = {met['RMSE_kW']} kW\nR² = {met['R2']}")
    ax.text(0.99, 0.96, txt, transform=ax.transAxes, ha="right", va="top", fontsize=9,
            bbox=dict(boxstyle="round", fc="white", ec="#bbb"))
    ax.set_title("Previsão de geração solar (regressão linear) no dia simulado", fontweight="bold", color=COR_TXT)
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------------
def _caixa(ax, x, y, w, h, texto, cor, fs=9.5, tcor="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                fc=cor, ec="#222", lw=1.1))
    ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center", fontsize=fs, color=tcor, fontweight="bold")


def _seta(ax, p1, p2, cor="#222", estilo="-", duplo=False):
    ax.annotate("", xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle="<->" if duplo else "->", color=cor, lw=1.8, ls=estilo))


def arquitetura(caminho):
    fig, ax = plt.subplots(figsize=(15, 8.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(-2, 66)
    ax.axis("off")

    # faixas das camadas
    for y, h, nome, cor in [(41, 22, "CAMADA DE DADOS E IA", "#eef3ff"),
                            (22, 15, "CAMADA DE BORDA (ESP32 + sensores + atuadores)", "#fff6e5"),
                            (-1, 21, "CAMADA FÍSICA (energia)", "#eaf7ef")]:
        ax.add_patch(FancyBboxPatch((0.5, y), 99, h, boxstyle="round,pad=0.2,rounding_size=1", fc=cor, ec="#bbb", lw=1))
        ax.text(1.5, y + h - 1.6, nome, fontsize=9.5, color="#555", fontweight="bold", va="center")

    # --- dados/IA ---
    _caixa(ax, 3, 52, 21.5, 7, "Previsão solar (IA)\nregressão linear", "#3b6fd4", fs=8.8)
    _caixa(ax, 27, 52, 21.5, 7, "Gerenciador de energia\n(agente inteligente)", "#3b6fd4", fs=8.8)
    _caixa(ax, 51, 52, 21.5, 7, "Dashboard e logs\n(CSV, gráficos, faturamento)", "#3b6fd4", fs=8.3)
    _caixa(ax, 75, 52, 22, 7, "CHATBOT ChargeGrid\n(LLM + memória)", "#c2185b", fs=8.8)
    _caixa(ax, 4, 42.5, 92, 5.5, "BROKER MQTT — tópicos  estacao/pv · estacao/bateria · estacao/porta/N/{cmd,medicao,evento}", "#1f3f8f", fs=9.5)
    for x in (13.75, 37.75, 61.75, 86):
        _seta(ax, (x, 52), (x, 48), cor="#1f3f8f" if x != 86 else "#c2185b", estilo="--", duplo=True)

    # --- borda ---
    _caixa(ax, 6, 24, 26, 8, "Sensores\ntensão/corrente · irradiância", "#e08a00", fs=9)
    _caixa(ax, 37, 24, 26, 8, "ESP32 (gateway de borda)\nleitura + envio de comandos", "#e08a00", fs=9)
    _caixa(ax, 68, 24, 27, 8, "Atuadores\ncontator · PWM Control Pilot", "#e08a00", fs=9)
    _seta(ax, (50, 32), (50, 42.5), cor="#1f3f8f", estilo="--", duplo=True)
    _seta(ax, (32, 28), (37, 28), cor="#e08a00")
    _seta(ax, (63, 28), (68, 28), cor="#e08a00")

    # --- fisica ---
    _caixa(ax, 3, 3.5, 17, 7.5, "Painéis FV\n30 kWp + inversor", COR_SOLAR, fs=9)
    _caixa(ax, 23, 3.5, 17, 7.5, "Bateria 20 kWh\n+ BMS", COR_BAT, fs=9)
    _caixa(ax, 43, 3.5, 17, 7.5, "Rede elétrica\n(limite 22 kW)", COR_REDE, fs=9)
    _caixa(ax, 66, 3.5, 17, 7.5, "4 carregadores\nEVSE 7,4 kW", "#7a4fd1", fs=9)
    _caixa(ax, 86, 3.5, 12, 7.5, "Veículos\nelétricos", "#444", fs=9)
    ax.add_patch(FancyBboxPatch((3, 13.6), 95, 2.2, boxstyle="round,pad=0.1,rounding_size=0.5", fc="#cfd8dc", ec="#222"))
    ax.text(50.5, 14.7, "BARRAMENTO CA 220 V", ha="center", va="center", fontsize=9, fontweight="bold", color=COR_TXT)
    _seta(ax, (11.5, 11), (11.5, 13.6), cor="#2a2a2a")                      # FV -> barramento
    _seta(ax, (31.5, 11), (31.5, 13.6), cor="#2a2a2a", duplo=True)          # bateria <-> barramento
    _seta(ax, (51.5, 11), (51.5, 13.6), cor="#2a2a2a", duplo=True)          # rede <-> barramento
    _seta(ax, (74.5, 13.6), (74.5, 11), cor="#2a2a2a")                      # barramento -> EVSE
    _seta(ax, (83, 7.2), (86, 7.2), cor="#2a2a2a")                          # EVSE -> veiculo

    # sensores leem o barramento; atuadores comandam EVSE
    _seta(ax, (28, 15.8), (28, 24), cor="#e08a00", estilo="--")
    _seta(ax, (80, 24), (80, 15.8), cor="#e08a00", estilo="--")

    ax.text(50, 64.3, "ChargeGrid Intelligence (SolarCharge AI) — arquitetura de integração", ha="center", fontsize=15, fontweight="bold", color=COR_TXT)
    ax.text(99, -1.7, "linha contínua = fluxo de energia   |   tracejada = fluxo de dados/comandos",
            ha="right", fontsize=8.5, color="#555")
    fig.savefig(caminho, dpi=140, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------
def _linha(ax, pontos, cor="#222", seta=True, estilo="-"):
    xs, ys = zip(*pontos)
    if len(pontos) > 2:
        ax.plot(xs[:-1], ys[:-1], color=cor, lw=1.8, ls=estilo)
    ax.annotate("", xy=pontos[-1], xytext=pontos[-2],
                arrowprops=dict(arrowstyle="->" if seta else "-", color=cor, lw=1.8, ls=estilo))


def fluxograma_chatbot(caminho):
    from matplotlib.patches import Polygon
    fig, ax = plt.subplots(figsize=(15, 8))
    ax.set_xlim(0, 100)
    ax.set_ylim(-3, 52)
    ax.axis("off")
    ax.text(50, 50, "Fluxograma do chatbot ChargeGrid Intelligence (entrada → processamento pelo LLM → resposta)",
            ha="center", fontsize=13.5, fontweight="bold", color=COR_TXT)

    # linha 1
    _caixa(ax, 2, 33, 15, 10, "Operador\ncomercial\n(pergunta)", "#444", fs=9.5)
    _caixa(ax, 21, 33, 15, 10, "Interface\nterminal / web", "#e08a00", fs=9.5)
    _caixa(ax, 40, 33, 17, 10, "Roteador de\nintenção +\nmemória (histórico)", "#3b6fd4", fs=9)
    ax.add_patch(Polygon([(72, 45), (82, 38), (72, 31), (62, 38)], closed=True, fc="#fff3cd", ec="#222", lw=1.2))
    ax.text(72, 38, "Dentro do\nescopo e há\ndados?", ha="center", va="center", fontsize=8.8, fontweight="bold", color=COR_TXT)
    _caixa(ax, 86, 33, 13, 10, "Resposta padrão\n(fora do escopo /\nsem dados)", "#8d6e63", fs=8)
    _linha(ax, [(17, 38), (21, 38)])
    _linha(ax, [(36, 38), (40, 38)])
    _linha(ax, [(57, 38), (62, 38)])
    _linha(ax, [(82, 38), (86, 38)])
    ax.text(83.8, 39.3, "Não", fontsize=8.5, color="#8d6e63", fontweight="bold", ha="center")
    ax.text(73.2, 29.3, "Sim", fontsize=8.5, color=COR_BAT, fontweight="bold")

    # linha 2 (da direita para a esquerda)
    _caixa(ax, 63, 17, 22, 9, "Consulta dados da estação\n(telemetria · sessões ·\nfaturamento · previsão)", "#2e7d32", fs=8.6)
    _caixa(ax, 38, 17, 21, 9, "Monta o prompt:\nsystem prompt +\nhistórico + dados", "#3b6fd4", fs=9)
    _caixa(ax, 13, 17, 21, 9, "LLM (Gemini)\ntemperatura 0,2\nresponde só com os dados", "#c2185b", fs=8.8)
    _linha(ax, [(72, 31), (72, 26)])
    _linha(ax, [(63, 21.5), (59, 21.5)])
    _linha(ax, [(38, 21.5), (34, 21.5)])

    # linha 3
    _caixa(ax, 13, 2, 21, 9, "Resposta\ncontextualizada\nao operador", "#444", fs=9)
    _caixa(ax, 38, 2, 21, 9, "Atualiza a memória\n(histórico e última\nsessão consultada)", "#3b6fd4", fs=8.6)
    _linha(ax, [(23.5, 17), (23.5, 11)])
    _linha(ax, [(34, 6.5), (38, 6.5)])
    # resposta padrao -> atualiza memoria
    _linha(ax, [(92.5, 33), (92.5, 6.5), (59, 6.5)], cor="#8d6e63")
    # resposta -> operador
    _linha(ax, [(13, 6.5), (9.5, 6.5), (9.5, 33)], cor="#444")
    ax.text(8.0, 20, "resposta volta ao operador", fontsize=8.5, color="#444", va="center", ha="center", rotation=90)
    ax.text(50, -2, "O LLM nunca inventa números: tudo que ele cita vem do bloco de dados injetado pelo sistema (dados simulados da estação).",
            ha="center", fontsize=9, color="#555")
    fig.savefig(caminho, dpi=140, bbox_inches="tight")
    plt.close(fig)
