# ⚡☀️ ChargeGrid Intelligence — Estação de Recarga Solar com IA e Chatbot Operacional

**EV Challenge 2026 · GoodWe · Sprint 3 — Prototipagem Funcional e Integração**

> Protótipo **simulado** que integra **energia solar + bateria + rede**, **carregadores de veículos elétricos**, **mensageria MQTT**, um **agente de IA** que orquestra a potência (com previsão solar por aprendizado de máquina) e um **chatbot com LLM** que comunica ao operador comercial o que a estação está fazendo.

- 🎥 **Vídeo técnico (YouTube, não listado):** `<<COLE AQUI O LINK DO VÍDEO>>`
- 💻 **Repositório:** `<<COLE AQUI O LINK DO GITHUB>>`

---

## 1. Equipe

| Nome completo | RM |
|---|---|
| `<<NOME 1>>` | `<<RM 1>>` |
| `<<NOME 2>>` | `<<RM 2>>` |
| `<<NOME 3>>` | `<<RM 3>>` |
| `<<NOME 4>>` | `<<RM 4>>` |

**Disciplina:** Inteligência Artificial · **Turma/Professor:** `<<PREENCHER>>`

---

## 2. Problema, contexto escolhido e persona

**Problema central do desafio (GoodWe):** os eletropostos não têm mecanismos **integrados** para **orquestrar potência**, **registrar ciclos** de recarga, **faturar** e **comunicar**.

**Contexto escolhido: ChargeGrid Intelligence (operação comercial).** Justificativa: o nosso protótipo já orquestra potência entre solar, bateria e rede, registra cada sessão e calcula o faturamento. Falta a peça de comunicação, e é ela que o chatbot resolve. O contexto condominial (EV ChargeOps) exigiria regras de rateio entre moradores que não são o foco desta entrega.

**Persona atendida: o operador comercial da estação**, quem responde pelo resultado financeiro e pela operação diária, e precisa de respostas rápidas como "quanto faturei hoje?", "por que a sessão 6 usou tanta rede?" ou "vale a pena a IA?", sem abrir planilhas nem logs.

| Pilar do problema | Como o protótipo resolve | Onde está no código |
|---|---|---|
| **Orquestrar potência** | Agente inteligente decide a cada 5 min a fonte (solar → bateria → rede) e a potência de cada carregador, com previsão solar por IA | `src/station.py`, `src/pv.py` |
| **Registrar ciclos** | Cada sessão registra SoC, horários e kWh por fonte; toda mensagem MQTT é gravada | `data/sessoes.csv`, `data/mqtt_log_*.jsonl` |
| **Faturar** | Receita = kWh entregue × preço de venda; custo da rede e margem por sessão e no dia | `src/main.py`, `data/sessoes.csv` |
| **Comunicar** | Chatbot com LLM responde ao operador com base nos dados reais da estação | `src/chatbot/`, `src/chat.py` |

## 3. Evolução das Sprints

| Sprint | Entrega | Onde está neste repositório |
|---|---|---|
| **1 — Planejamento** | Escopo e persona, tecnologias, fluxograma, **modelo de teste (≥ 5 perguntas)** e **system prompt** | seções 2, 5 e 6 · `docs/fluxograma_chatbot.png` · `docs/modelo_de_teste.md` · `prompts/system_prompt.txt` |
| **2 — Chatbot** | Chatbot funcional com system prompt, **memória de contexto** e validação pelo modelo de teste | `src/chatbot/` · `python src/chat.py` · seção 8.5 |
| **3 — Integração** | Chatbot integrado à estação solar simulada (dados, sessões, faturamento, previsão) e demonstração do sistema completo | todo o repositório |

> `<<Se as Sprints 1 e 2 do grupo tiveram decisões diferentes (outro LLM, outro contexto, outro nome de projeto), ajuste esta seção e a 5.>>`

---

## 4. Esquema de integração dos componentes

### 4.1 Diagrama de blocos

![Arquitetura](docs/arquitetura.png)

### 4.2 Como cada componente se conecta

| Componente | Papel na integração | Como aparece na simulação (`src/`) | Hardware de referência* |
|---|---|---|---|
| **Painéis FV + inversor** | Geram a energia renovável | `pv.py` → curva solar com nuvens (30 kWp) | Inversor híbrido solar |
| **Sensor de potência FV** | Mede a geração e publica em `estacao/pv/potencia` | `SensorPV` (ruído de 2%) | Leitura Modbus do inversor ou sensor V/I |
| **Bateria estacionária + BMS** | Guarda excedente solar; entrega à noite | `Bateria` (20 kWh, SoC 20–90%) | Bateria de lítio com BMS |
| **Rede elétrica** | Garante a meta de carga (limite 22 kW) | coluna `rede_para_ev_kw` | Ponto de conexão da concessionária |
| **Carregadores (EVSE)** | Recebem comandos; medem kWh; ligam/desligam | `Carregador` (4 portas, 7,4 kW) | EVSE AC + contator + PWM *Control Pilot* |
| **ESP32 (borda)** | Lê sensores e executa comandos | papel simulado pelas classes acima | ESP32 DevKit |
| **Broker MQTT** | Desacopla todos os componentes | `bus.py` (mesmos tópicos do MQTT real) | Mosquitto |
| **Previsor solar (IA)** | Prevê a geração do dia | `PrevisorSolar` em `pv.py` | Serviço em borda/nuvem |
| **Gerenciador de energia (agente)** | Decide potência e fonte de cada recarga | `ControladorInteligente` em `station.py` | Serviço em borda/nuvem |
| **Faturamento e logs** | Registra ciclos e calcula receita/custo/margem | `main.py` → `data/*.csv` | Backend de cobrança (OCPP/CSMS) |
| **Chatbot ChargeGrid (LLM)** | Responde ao operador usando os dados acima | `src/chatbot/` | Interface web / WhatsApp / painel |

\* *Hardware de referência descreve como seria a montagem física. **Nesta Sprint o protótipo é totalmente simulado**; nenhum circuito foi montado.*

**Esquema elétrico de referência (ESP32):** UART2 (GPIO16/17) ↔ medidor de energia de cada carregador · GPIO26 → módulo de relé que aciona o contator · GPIO25 (PWM 1 kHz) → circuito *Control Pilot* · GPIO34 (ADC) ← leitura do nível do *Control Pilot* · GPIO2 → LED de status · Wi-Fi → broker MQTT.

### 4.3 Tópicos e mensagens MQTT

| Tópico | Quem publica | Quem assina | Exemplo |
|---|---|---|---|
| `estacao/pv/potencia` | Sensor FV | Controlador | `{"kw": 17.9}` |
| `estacao/bateria/estado` | BMS | Controlador | `{"soc": 0.9, "max_descarga_kw": 10.0, "max_carga_kw": 0.0}` |
| `estacao/porta/N/evento` | Carregador | Controlador | `{"evento":"VEICULO_CONECTADO","cap_kwh":40,"soc":0.2,"soc_alvo":0.9,"saida_h":16.0}` |
| `estacao/porta/N/medicao` | Carregador | Controlador | `{"kw": 7.4, "soc": 0.35, "kwh": 5.2}` |
| `estacao/ia/previsao_solar` | Previsor (IA) | Controlador | `{"kw_5min": [0.0, 0.0, ...]}` |
| `estacao/porta/N/cmd` | Controlador | Carregador | `{"cmd":"START","kw":7.4,"fontes":{"solar":7.4,"bateria":0.0,"rede":0.0}}` |
| `estacao/bateria/cmd` | Controlador | Bateria | `{"carga_kw": 3.2, "descarga_kw": 0.0}` |

Trecho real do log (`data/mqtt_log_proposta.jsonl`): um carro chega às 08:00 e o agente aciona a recarga só com solar.

```json
{"hora": "08:00", "topico": "estacao/porta/1/evento", "payload": {"evento": "VEICULO_CONECTADO", "veiculo": "Hatch compacto 40 kWh", "cap_kwh": 40, "soc": 0.2, "soc_alvo": 0.9, "saida_h": 16.0}}
{"hora": "08:00", "topico": "estacao/porta/1/cmd", "payload": {"cmd": "START", "kw": 7.4, "fontes": {"solar": 7.4, "bateria": 0.0, "rede": 0.0}}}
```

### 4.4 Lógica do agente de energia

```mermaid
flowchart TD
    A["A cada 5 min: ler telemetria (FV, bateria, veículos)"] --> B["Para cada veículo: energia que falta e tempo restante"]
    B --> C["IA: solar previsto até a hora de saída (dividido entre veículos ativos)"]
    C --> D["déficit = falta − 80% do solar previsto"]
    D --> E{"Sessão crítica?<br/>falta ≥ 85% da potência máx × tempo restante"}
    E -- Sim --> F["Libera potência máxima<br/>solar → bateria → rede"]
    E -- Não --> G["Usa solar disponível primeiro"]
    G --> H{"déficit > 0 e sem sol?"}
    H -- Sim --> I["Usa bateria"]
    H -- Não --> J["Rede limitada a 1,15 × déficit ÷ tempo restante"]
    I --> J
    F --> K["Publica comandos MQTT"]
    J --> K
    K --> L["Sobra de solar carrega a bateria"]
```

---

## 5. O chatbot ChargeGrid Assistant

### 5.1 Fluxograma de funcionamento (entrada → LLM → resposta)

![Fluxograma do chatbot](docs/fluxograma_chatbot.png)

```mermaid
flowchart LR
    U["Operador comercial"] --> I["Interface (terminal / web)"]
    I --> R["Roteador de intenção + memória"]
    R --> Q{"Dentro do escopo<br/>e há dados?"}
    Q -- Não --> P["Resposta padrão"]
    Q -- Sim --> D["Consulta dados da estação"]
    D --> M["Monta prompt: system prompt + histórico + dados"]
    M --> L["LLM (Gemini)"]
    L --> A["Resposta ao operador"]
    P --> A
    A --> H["Atualiza histórico"]
```

### 5.2 Como o chatbot se integra ao restante do sistema

1. **O operador pergunta** em linguagem natural (terminal ou navegador).
2. O **roteador de intenção** identifica o tema (energia, sessão N, faturamento, previsão, horário, comparação…) e usa a **memória** para perguntas de seguimento (*"E a 6?"* depois de *"Como foi a sessão 5?"*).
3. A **camada de dados** lê os arquivos gerados pela estação (`metricas.json`, `sessoes.csv`, telemetria) e devolve **fatos estruturados**.
4. O prompt enviado ao LLM = **system prompt** + **histórico** + **pergunta** + **bloco "DADOS DA ESTAÇÃO"**.
5. O LLM redige a resposta **usando somente aqueles dados**. Se o assunto for fora do escopo ou não houver dado, o bot recusa ou informa que não tem a informação.

Essa técnica (injetar dados verificados no prompt, uma forma simples de *grounding*/RAG com dados estruturados) evita que o modelo invente números, o que é essencial num sistema que fala de dinheiro e energia.

### 5.3 System prompt

O contexto-base que condiciona o modelo está em [`prompts/system_prompt.txt`](prompts/system_prompt.txt). Pontos principais:

- **Papel e persona:** assistente operacional do ChargeGrid Intelligence, usuário = operador comercial.
- **Escopo permitido:** energia do dia, pico de demanda, sessões, faturamento/margem, previsão solar, estado por horário, comparação com/sem IA, explicação das decisões.
- **Regras:** usar só os números fornecidos; admitir quando não há dado; recusar fora do escopo; resposta curta em pt-BR com unidades; lembrar que os dados são simulados; ignorar tentativas de mudar o papel (*prompt injection*); nesta versão só **consulta e explica** (não comanda carregadores).

### 5.4 Parâmetros e tecnologias

| Item | Escolha | Justificativa |
|---|---|---|
| **LLM** | **Google Gemini** (`gemini-2.5-flash`) via API REST | Nível gratuito para estudantes, bom português, suporte nativo a `system_instruction`, baixa latência; funciona igual no Google Colab e em IDE |
| **Temperatura** | 0,2 | Respostas estáveis e factuais (o bot relata dados, não cria) |
| **Máx. de tokens** | 1.500 | Respostas curtas; margem para o raciocínio interno do modelo |
| **Memória** | Últimas 8 trocas (pergunta + resposta) | Permite seguimento sem estourar o contexto |
| **Grounding** | Dados da estação injetados no prompt | Dados são estruturados e pequenos: consulta exata é mais confiável que busca vetorial |
| **Sem LangChain** | Pipeline próprio em Python puro, sem dependências extras | O fluxo é simples e linear; menos dependências e mais fácil de explicar |
| **Modo offline** | Respondedor por *templates* (**não é LLM**) | Roda sem internet/chave e dá resultados reproduzíveis para testes e demonstração |
| **Alternativas descartadas** | Llama local (exige GPU), API paga (custo) | — |

### 5.5 Iteração do prompt e dos parâmetros

Registre aqui os ajustes feitos após testar com o Gemini (`python src/chat.py --backend gemini --teste`):

| Iteração | Problema observado nos testes | Mudança no prompt/parâmetro | Resultado |
|---|---|---|---|
| `<<1>>` | `<<PREENCHER>>` | `<<PREENCHER>>` | `<<PREENCHER>>` |

---

## 6. Justificativa técnica das escolhas (sistema completo)

| Escolha | Por quê | Alternativa descartada |
|---|---|---|
| **ESP32 como gateway de borda** | Wi-Fi nativo, ADC e PWM (necessário para o *Control Pilot* de 1 kHz), custo baixo | Arduino Uno (sem Wi-Fi); Raspberry Pi (mais caro para uma tarefa simples) |
| **MQTT (publicar/assinar)** | Leve, padrão IoT, **desacopla** sensores, IA e atuadores e permite trocar a simulação pelo hardware real | HTTP direto entre módulos (acoplamento e mais tráfego) |
| **Regressão linear para prever o sol** | Poucos dados, **interpretável** (3 pesos), cabe até em microcontrolador, erro medido em teste | LSTM/redes profundas (exigem muito mais dados para o ganho neste problema) |
| **Agente com regras + previsão** | **Garante** as restrições (meta de SoC até a saída, limite da rede); decisões explicáveis, o que o chatbot aproveita | Aprendizado por reforço (milhares de episódios; não garante a meta de carga) |
| **Bateria estacionária** | Desloca o sol do meio-dia para o fim da tarde/noite | Só painéis (excedente do meio-dia desperdiçado) |
| **Chatbot com dados injetados** | Evita "alucinação" de números e mantém o bot dentro do escopo operacional | LLM sem dados (inventaria valores) |
| **Passo de 5 minutos** | Acompanha a variação de nuvens e a telemetria típica | Passo de 1 h (perde variações rápidas) |
| **Simulação em Python** | Reprodutível (`SEED` fixa), compara dois cenários no mesmo dia | Montagem física (fora do escopo/prazo) |

---

## 7. Como o chatbot aparece na demonstração

Trecho real gerado por `python src/chat.py --demo` (modo offline). Com `GEMINI_API_KEY` definida, o mesmo fluxo é redigido pelo LLM. Conversa completa em [`docs/exemplo_conversa_offline.md`](docs/exemplo_conversa_offline.md).

> **👤 Operador:** Como foi a sessão 5?
> **🤖 Assistente:** Sessão 5 (porta 1, Sedan elétrico 50 kWh): chegou às 17:00 e saiu às 22:00; SoC de 20% para 70% (meta 70%, atingida: sim). Energia: 1,4 kWh de solar, 10,7 kWh da bateria e 15,1 kWh da rede (44,6% renovável); faturamento de R$ 59,78. Sessão no período noturno, sem geração solar. O gerenciador usou a bateria primeiro e a rede só para completar o déficit e cumprir a meta até a hora de saída.
>
> **👤 Operador:** E a 6? *(memória de contexto)*
> **🤖 Assistente:** Continuando sobre as sessões: Sessão 6 (porta 3, Utilitário 35 kWh): chegou às 18:30 e saiu às 23:00; SoC de 15% para 65% (meta 65%, atingida: sim). Energia: 0,0 kWh de solar, 1,5 kWh da bateria e 17,5 kWh da rede (8,0% renovável); faturamento de R$ 41,85. …
>
> **👤 Operador:** Qual é a capital da França?
> **🤖 Assistente:** Sou o assistente do ChargeGrid Intelligence e só respondo sobre a operação desta estação de recarga […]. Esse assunto está fora do meu escopo. Quer um resumo do dia?

---

## 8. Resultados e dados funcionais

> ⚠️ **Todos os números são de SIMULAÇÃO** (1 dia, 6 sessões fictícias, clima sintético, semente `42`). Rodando `python src/main.py` você obtém exatamente os mesmos valores. Tarifa da rede (R$ 0,95/kWh), preço de venda (R$ 2,20/kWh) e fator de CO₂ (0,06 kg/kWh) são **valores ilustrativos** editáveis em `src/config.py`.

### 8.1 Modelo de IA: previsão da geração solar

![Previsão solar](docs/previsao_solar.png)

| Métrica (30 dias de teste, não vistos no treino) | Valor |
|---|---|
| MAE | 0,83 kW |
| RMSE | 1,65 kW |
| R² | 0,93 |
| Erro médio na energia diária | 14,6 % |

### 8.2 Um dia de operação (solar + bateria + IA)

![Dia da proposta](docs/resultado_dia_proposta.png)

- Sessões 1 a 3 (dia): recarregadas quase 100% com solar direto.
- O excedente do meio-dia leva a bateria de 20% a 90% (painel de baixo).
- Sessões 5 e 6 (noite): usam a bateria primeiro e a rede só no necessário; a sessão 6 fecha a meta **exatamente na hora de sair**.

### 8.3 Sessões, ciclos registrados e faturamento (`data/sessoes.csv`)

| Sessão | Porta | Veículo | Janela | SoC (início → final) | Solar (kWh) | Bateria (kWh) | Rede (kWh) | Faturamento | Margem |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | Hatch compacto 40 kWh | 08:00–16:00 | 20% → 90% (meta 90%) | 30,37 | 0,00 | 0,06 | R$ 66,95 | R$ 66,90 |
| 2 | 2 | SUV elétrico 60 kWh | 09:30–13:30 | 30% → 65% (meta 65%) | 22,73 | 0,00 | 0,09 | R$ 50,21 | R$ 50,12 |
| 3 | 3 | Sedan elétrico 50 kWh | 11:00–15:00 | 25% → 70% (meta 70%) | 24,36 | 0,00 | 0,09 | R$ 53,80 | R$ 53,71 |
| 4 | 2 | Hatch compacto 40 kWh | 14:00–18:30 | 35% → 90% (meta 90%) | 19,46 | 1,10 | 3,35 | R$ 52,61 | R$ 49,43 |
| 5 | 1 | Sedan elétrico 50 kWh | 17:00–22:00 | 20% → 70% (meta 70%) | 1,43 | 10,68 | 15,07 | R$ 59,78 | R$ 45,47 |
| 6 | 3 | Utilitário 35 kWh | 18:30–23:00 | 15% → 65% (meta 65%) | 0,00 | 1,52 | 17,51 | R$ 41,85 | R$ 25,22 |

**Todas as 6 metas de carga foram atingidas até a hora de saída.**

### 8.4 Comandos automatizados, coleta e exibição de dados

| Item | Baseline | Proposta |
|---|---|---|
| Mensagens MQTT no dia | 1.291 | 1.643 |
| Comandos aos carregadores (`START`/`SET_POWER`/`STOP`) | 55 | 118 |
| Telemetria a cada 5 min (288 linhas/dia) | `data/telemetria_baseline.csv` | `data/telemetria_proposta.csv` |
| Log completo de mensagens | `data/mqtt_log_baseline.jsonl` | `data/mqtt_log_proposta.jsonl` |
| Exibição para o operador | — | Chatbot (terminal/web) + gráficos em `docs/` |

### 8.5 Validação do chatbot com o modelo de teste

O modelo de teste (`tests/modelo_de_teste.json` → [`docs/modelo_de_teste.md`](docs/modelo_de_teste.md)) tem **12 casos**: consulta de energia, pico, faturamento, detalhe de sessão, **memória de contexto**, previsão, estado por horário, comparação, **pergunta fora do escopo**, **pergunta sem dados** (não inventar), explicação de decisão e **tentativa de manipulação do prompt**. Cada caso tem resposta ideal e critérios automáticos (números e frases que devem ou não aparecer).

| Backend | Testes aprovados | Critérios cumpridos | Observação |
|---|---|---|---|
| Offline (templates, **não é LLM**) | **12/12** | 36/36 | Valida o roteador, a camada de dados, a memória e o próprio teste. O teste foi verificado também com um backend propositalmente ruim, que foi reprovado (0/12). |
| Gemini (LLM real) | `<<RODE: python src/chat.py --backend gemini --teste e preencha>>` | `<<...>>` | Resultados em `data/teste_chatbot_gemini.csv` |

> O resultado do modo offline **não prova** que o LLM se comporta bem; ele mostra que a infraestrutura de teste funciona. A avaliação do comportamento do LLM é a linha do Gemini.

### 8.6 Comparação: sem IA × com IA (mesmo dia, mesmas sessões)

![Comparativo](docs/comparativo.png)

| Indicador | Baseline (solar + rede, sem bateria, sem IA) | Proposta (solar + bateria + IA) | Diferença |
|---|---|---|---|
| Energia entregue aos veículos | 147,8 kWh | 147,8 kWh | igual |
| Energia da rede | 52,1 kWh | 36,2 kWh | **−30,5 %** |
| Fração renovável | 64,8 % | 75,5 % | **+10,7 p.p.** |
| Pico de potência da rede | 14,8 kW | 8,9 kW | **−40 %** |
| Excedente solar desperdiçado | 43,4 kWh | 26,0 kWh | −17,4 kWh |
| Faturamento do dia | R$ 325,20 | R$ 325,21 | igual (mesma energia entregue) |
| Custo da energia da rede | R$ 49,50 | R$ 34,36 | −R$ 15,14 |
| Margem do dia | R$ 275,70 | R$ 290,85 | +R$ 15,15 |
| CO₂ da rede | 3,13 kg | 2,17 kg | −0,96 kg |
| Metas de carga atingidas | 6/6 | 6/6 | igual |

---

## 9. Sustentabilidade, automação inteligente e eficiência energética

- **Sustentabilidade:** a fração renovável nas recargas sobe de 64,8% para 75,5% e o CO₂ da rede cai ~31% no dia simulado; a bateria aproveita parte do excedente solar.
- **Automação inteligente:** o agente lê o ambiente, planeja e comanda os carregadores sozinho (118 comandos no dia) respeitando a meta e a hora de saída de cada motorista; o chatbot traduz tudo em linguagem natural para o operador.
- **Eficiência energética:** menos energia comprada da rede, **pico de demanda 40% menor** e uso do sol quando ele existe.

## 10. Conexão com os conteúdos da disciplina

> `<<Ajuste esta seção aos tópicos exatos vistos em aula.>>`

| Conteúdo | Onde aparece |
|---|---|
| **Modelos de linguagem (LLMs) e engenharia de prompt** | `prompts/system_prompt.txt`; Gemini com `system_instruction`, temperatura 0,2 |
| **Grounding / RAG com dados estruturados** | Bloco "DADOS DA ESTAÇÃO" injetado no prompt; o LLM só cita números fornecidos |
| **Memória de contexto em chatbots** | Histórico das últimas 8 trocas + resolução de seguimentos (*"E a 6?"*) |
| **Avaliação de sistemas de IA** | Modelo de teste com 12 casos e critérios automáticos; testes de escopo, alucinação e injeção |
| **Agentes inteligentes** (percepção → decisão → ação) | `ControladorInteligente`: telemetria → planejamento → comandos MQTT |
| **Aprendizado supervisionado** (regressão, treino/teste, MAE/RMSE/R²) | `PrevisorSolar`: 120 dias de treino, 30 de teste |
| **IA aplicada a IoT / sistemas ciberfísicos** | Sensores → MQTT → IA → atuadores |

---

## 11. Como executar

Requisitos: Python 3.10+.

```bash
git clone <<URL-DO-REPOSITORIO>>
cd <<nome-da-pasta>>
pip install -r requirements.txt

python src/main.py                      # 1) simula a estação e gera dados e gráficos
python src/chat.py --demo               # 2) conversa de demonstração com o chatbot
python src/chat.py                      #    ou converse no terminal
python src/chat.py --web                #    ou abra a interface web (http://localhost:8000)
python src/chat.py --teste              # 3) roda o modelo de teste do chatbot
```

**Usar o LLM real (Gemini):** gere uma chave gratuita em [aistudio.google.com](https://aistudio.google.com) e defina a variável antes de rodar.

```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="SUA_CHAVE"
python src/chat.py --backend gemini --web

# Mac / Linux
export GEMINI_API_KEY="SUA_CHAVE"
python src/chat.py --backend gemini --web
```

Sem a chave, o chatbot roda em **modo offline** (templates, sem LLM). **Nunca coloque a chave no código nem no GitHub.**

**Google Colab:** em uma célula: `!git clone <URL> && cd <pasta> && python src/main.py`; defina `os.environ["GEMINI_API_KEY"]` numa célula e use `!python src/chat.py --backend gemini --demo` (no Colab use `--demo` ou `--teste`, não o modo interativo).

## 12. Estrutura do repositório

```
├── README.md
├── requirements.txt
├── prompts/system_prompt.txt        ← contexto-base (system prompt) do chatbot
├── tests/modelo_de_teste.json       ← modelo de teste (perguntas, respostas ideais, critérios)
├── src/
│   ├── config.py                    ← parâmetros da simulação
│   ├── main.py                      ← simula a estação; gera dados e gráficos
│   ├── bus.py · pv.py · station.py · plots.py
│   ├── chat.py                      ← entrada do chatbot (terminal, web, demo, teste)
│   └── chatbot/                     ← dados · intents · backends · bot · teste · web
├── data/                            ← telemetria, sessões, métricas, logs MQTT, resultados de teste
└── docs/                            ← diagramas, fluxograma, gráficos, modelo de teste, conversa de exemplo
```

## 13. Limitações e próximos passos

- **Dados simulados:** 1 dia, clima sintético e sessões fictícias; os ganhos valem para este cenário e não são promessa para uma instalação real.
- O ganho vem do **conjunto** bateria + previsão + planejamento; não isolamos cada parte (estudo de ablação é um próximo passo).
- O chatbot **só consulta e explica**; ele ainda não envia comandos aos carregadores nem lê dados em tempo real (lê os arquivos gerados pela simulação). O roteador de intenção é por regras; um LLM com *function calling* poderia substituí-lo.
- O **modo offline não é um LLM**; o comportamento real do LLM deve ser avaliado com o Gemini (seção 8.5).
- Ainda sobram 26 kWh de excedente solar: bateria maior, mais sessões diurnas ou injeção na rede (V2G) melhorariam o aproveitamento.
- **Próximos passos:** montar o circuito com ESP32 + medidor + contator; trocar `BarramentoMQTT` por `paho-mqtt` + Mosquitto; previsão do tempo real; OCPP; contexto condominial (EV ChargeOps).
