# Exemplo de conversa (backend: offline)

Gerado por `python src/chat.py --demo`. Dados simulados.

**👤 Operador:** Oi, o que você faz?

**🤖 Assistente** _(tema: ajuda)_: Olá! Sou o assistente do ChargeGrid Intelligence. Posso informar: energia do dia (solar, bateria, rede), pico de demanda, detalhes de cada sessão de recarga, faturamento e margem, previsão solar, estado da estação em um horário (ex.: 19:00) e a comparação com e sem IA. O que você quer saber?

**👤 Operador:** Quanto de energia da rede a estação consumiu hoje e quanto foi solar?

**🤖 Assistente** _(tema: energia)_: Hoje a estação entregou 147,8 kWh aos veículos: 98,4 kWh de solar direto, 13,3 kWh vindos da bateria e 36,2 kWh da rede. Isso dá 75,5% de energia renovável. A usina gerou 139,1 kWh e 26,0 kWh de excedente não foram aproveitados. (Dados simulados.)

**👤 Operador:** Como foi a sessão 5?

**🤖 Assistente** _(tema: sessao)_: Sessão 5 (porta 1, Sedan eletrico 50 kWh): chegou às 17:00 e saiu às 22:00; SoC de 20% para 70% (meta 70%, atingida: sim). Energia: 1,4 kWh de solar, 10,7 kWh da bateria e 15,1 kWh da rede (44,6% renovável); faturamento de R$ 59,78. Sessão no período noturno, sem geração solar. O gerenciador usou a bateria primeiro e a rede só para completar o déficit e cumprir a meta até a hora de saída.

**👤 Operador:** E a 6?

**🤖 Assistente** _(tema: sessao)_: Continuando sobre as sessões: Sessão 6 (porta 3, Utilitario 35 kWh): chegou às 18:30 e saiu às 23:00; SoC de 15% para 65% (meta 65%, atingida: sim). Energia: 0,0 kWh de solar, 1,5 kWh da bateria e 17,5 kWh da rede (8,0% renovável); faturamento de R$ 41,85. Sessão no período noturno, sem geração solar. O gerenciador usou a bateria primeiro e a rede só para completar o déficit e cumprir a meta até a hora de saída.

**👤 Operador:** Quanto faturei hoje e qual foi a margem?

**🤖 Assistente** _(tema: financeiro)_: Faturamento do dia: R$ 325,21 (energia entregue × R$ 2,20/kWh). Custo da energia comprada da rede: R$ 34,36. Margem: R$ 290,85. Sem a IA o custo da rede seria R$ 49,50, ou seja, uma economia de R$ 15,14 no dia. Valores ilustrativos de uma simulação.

**👤 Operador:** Como estava a estação às 19:00?

**🤖 Assistente** _(tema: status)_: Às 19:00 havia 2 veículos conectados, recebendo 14,4 kW no total: 0,0 kW de solar, 10,0 kW da bateria e 4,4 kW da rede. A geração solar era 0,0 kW e a bateria estava com 21,9% de carga.

**👤 Operador:** Vale a pena usar IA e bateria? Compare com o cenário sem IA.

**🤖 Assistente** _(tema: comparativo)_: Comparando com o cenário sem IA e sem bateria (mesmo dia e mesmas sessões): a energia da rede caiu 30,5% (de 52,1 para 36,2 kWh), a fração renovável subiu de 64,8% para 75,5% (+10,7 p.p.) e o pico da rede caiu 40%. Economia de R$ 15,14 no dia e 0,96 kg de CO₂ evitados; metas de carga atingidas: 6/6. (Simulação.)

**👤 Operador:** Qual é a capital da França?

**🤖 Assistente** _(tema: fora_escopo)_: Sou o assistente do ChargeGrid Intelligence e só respondo sobre a operação desta estação de recarga: energia, sessões, faturamento, pico de demanda, previsão solar e comparação com e sem IA. Esse assunto está fora do meu escopo. Quer um resumo do dia?

**👤 Operador:** Quantos carros o condomínio Solar Park recarregou este mês?

**🤖 Assistente** _(tema: sem_dados)_: Não tenho dados sobre outros locais, condomínios ou unidades (só existem dados desta estação). Só disponho dos dados da estação simulada SolarCharge AI (1 dia, 6 sessões). Posso responder algo sobre ela?
