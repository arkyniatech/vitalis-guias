# Agosto, guia a guia

Gerado por `scripts/explicar_agosto.py` rodando o motor de verdade (sem IA, só o fallback por palavra-chave, pra ser reproduzível). Conferência no dia do lançamento de cada guia.

**80 guias · R$ 5.694,00 lançados · R$ 2.642,00 em risco (46% do lançado)**

bloqueada: 32 · pendente: 1 · corrigir: 6 · atencao: 5 · ok: 36

Nas bloqueadas, pendente e corrigir, cada achado mostra o que está errado e a ação. A observação da recepção aparece com a intenção que foi lida dela.


## Bloqueadas: não podem ir do jeito que estão (32)

- **G-2608-0002** · Sul · Plano Bem · Consulta ortopédica · sessão 1 · R$ 90,00 · **R$ 90,00 em risco**
  - Observação da recepção: "Trouxe exame novo, anexado ao prontuário." → lida como `sem_acao`
  - Procedimento não coberto pelo convênio (bloqueia): Plano Bem não cobre Consulta ortopédica (20103301). → Faturar como particular. Regra do Plano Bem: 'Não cobre consulta médica; consulta é faturada como particular.'
- **G-2608-0004** · Norte · Plano Bem · Sessão de fisioterapia musculoesquelética · sessão 8 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Trouxe exame novo, anexado ao prontuário." → lida como `sem_acao`
  - Autorização vencida (bloqueia): Autorização AUT222104 venceu em 04/08/2026 e o atendimento foi em 18/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
- **G-2608-0006** · Norte · Vitalcard · Infiltração articular · sessão 15 · R$ 140,00 · **R$ 140,00 em risco**
  - Observação da recepção: "Paciente chegou 10 min atrasado." → lida como `sem_acao`
  - Procedimento não coberto pelo convênio (bloqueia): Vitalcard não cobre Infiltração articular (40201015). → Não enviar ao Vitalcard. Confirmar com o paciente: particular ou outro convênio.
  - Sessão acima do limite da autorização (bloqueia): Sessão nº 15 numa autorização que cobre 10. → Precisa de nova autorização. Vitalcard cobre 10 sessões por autorização. (Reavaliação médica obrigatória a cada 10 sessões; nova autorização a cada reavaliação.)
- **G-2608-0007** · Centro · Vitalcard · Infiltração articular · sessão 1 · R$ 140,00 · **R$ 140,00 em risco**
  - Observação da recepção: "Pediu recibo para reembolso do plano." → lida como `reembolso`
  - Procedimento não coberto pelo convênio (bloqueia): Vitalcard não cobre Infiltração articular (40201015). → Não enviar ao Vitalcard. Confirmar com o paciente: particular ou outro convênio.
  - Pediu recibo pra reembolso (observação) (atencao): Recepção anotou: 'Pediu recibo para reembolso do plano.'. Reembolso é coisa de quem pagou particular. → Confirmar se essa guia vai mesmo pro Vitalcard ou se o paciente pagou direto.
- **G-2608-0008** · Sul · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 13 · R$ 70,00 · **R$ 70,00 em risco**
  - Observação da recepção: "Paciente chegou 10 min atrasado." → lida como `sem_acao`
  - Sessão acima do limite da autorização (bloqueia): Sessão nº 13 numa autorização que cobre 10. → Precisa de nova autorização. Vitalcard cobre 10 sessões por autorização. (Reavaliação médica obrigatória a cada 10 sessões; nova autorização a cada reavaliação.)
- **G-2608-0014** · Sul · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 8 · R$ 70,00 · **R$ 70,00 em risco**
  - Autorização vencida (bloqueia): Autorização AUT261365 venceu em 27/07/2026 e o atendimento foi em 17/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
- **G-2608-0021** · Norte · Vitalcard · Sessão de fisioterapia musculoesquelética · sessão 9 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Paciente chegou 10 min atrasado." → lida como `sem_acao`
  - Campo obrigatório vazio (bloqueia): Sem CID. Vitalcard exige. → Pedir o CID ao profissional que atendeu (está no pedido médico) e lançar antes de enviar.
- **G-2608-0023** · Norte · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 4 · R$ 70,00 · **R$ 70,00 em risco**
  - Observação da recepção: "Confirmado pelo WhatsApp na véspera." → lida como `sem_acao`
  - Autorização vencida (bloqueia): Autorização AUT819809 venceu em 25/07/2026 e o atendimento foi em 17/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
- **G-2608-0024** · Norte · Plano Bem · Consulta ortopédica · sessão 5 · R$ 90,00 · **R$ 90,00 em risco**
  - Observação da recepção: "Trouxe exame novo, anexado ao prontuário." → lida como `sem_acao`
  - Procedimento não coberto pelo convênio (bloqueia): Plano Bem não cobre Consulta ortopédica (20103301). → Faturar como particular. Regra do Plano Bem: 'Não cobre consulta médica; consulta é faturada como particular.'
- **G-2608-0026** · Norte · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 22 · R$ 62,00 · **R$ 62,00 em risco**
  - Sessão acima do limite da autorização (bloqueia): Sessão nº 22 numa autorização que cobre 20. → Precisa de nova autorização. Saúde Interior cobre 20 sessões por autorização.
- **G-2608-0028** · Norte · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 6 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Pediu recibo para reembolso do plano." → lida como `reembolso`
  - Autorização vencida (bloqueia): Autorização AUT457263 venceu em 18/08/2026 e o atendimento foi em 27/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
  - Pediu recibo pra reembolso (observação) (atencao): Recepção anotou: 'Pediu recibo para reembolso do plano.'. Reembolso é coisa de quem pagou particular. → Confirmar se essa guia vai mesmo pro Saúde Interior ou se o paciente pagou direto.
- **G-2608-0031** · Centro · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 3 · R$ 70,00 · **R$ 70,00 em risco**
  - Autorização vencida (bloqueia): Autorização AUT244662 venceu em 01/08/2026 e o atendimento foi em 04/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
- **G-2608-0032** · Sul · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 18 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Pediu recibo para reembolso do plano." → lida como `reembolso`
  - Autorização vencida (bloqueia): Autorização AUT265721 venceu em 26/07/2026 e o atendimento foi em 19/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
  - Pediu recibo pra reembolso (observação) (atencao): Recepção anotou: 'Pediu recibo para reembolso do plano.'. Reembolso é coisa de quem pagou particular. → Confirmar se essa guia vai mesmo pro Saúde Interior ou se o paciente pagou direto.
- **G-2608-0035** · Norte · Plano Bem · Consulta ortopédica · sessão 2 · R$ 90,00 · **R$ 90,00 em risco**
  - Procedimento não coberto pelo convênio (bloqueia): Plano Bem não cobre Consulta ortopédica (20103301). → Faturar como particular. Regra do Plano Bem: 'Não cobre consulta médica; consulta é faturada como particular.'
- **G-2608-0039** · Norte · Vitalcard · Sessão de fisioterapia musculoesquelética · sessão 3 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Paciente pediu para faturar como particular, não quer usar o convênio." → lida como `faturar_particular`
  - Paciente pediu particular (observação) (bloqueia): Recepção anotou: 'Paciente pediu para faturar como particular, não quer usar o convênio.'. → Não enviar ao Vitalcard. Lançar como particular.
- **G-2608-0045** · Norte · Plano Bem · Reavaliação fisioterapêutica · sessão 8 · R$ 55,00 · **R$ 55,00 em risco**
  - Profissional incompatível com o procedimento (bloqueia): Reavaliação fisioterapêutica exige fisioterapeuta (CREFITO), mas o profissional lançado é Dr. Otávio Prado (CRM-SP 97731). → Ou o profissional está errado, ou o procedimento. Conferir com quem atendeu.
- **G-2608-0046** · Norte · Vitalcard · Sessão de fisioterapia musculoesquelética · sessão 1 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Confirmado pelo WhatsApp na véspera." → lida como `sem_acao`
  - Autorização vencida (bloqueia): Autorização AUT308387 venceu em 18/08/2026 e o atendimento foi em 24/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
- **G-2608-0047** · Sul · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 14 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Pediu recibo para reembolso do plano." → lida como `reembolso`
  - Autorização vencida (bloqueia): Autorização AUT633684 venceu em 15/08/2026 e o atendimento foi em 27/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
  - Pediu recibo pra reembolso (observação) (atencao): Recepção anotou: 'Pediu recibo para reembolso do plano.'. Reembolso é coisa de quem pagou particular. → Confirmar se essa guia vai mesmo pro Saúde Interior ou se o paciente pagou direto.
- **G-2608-0049** · Norte · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 7 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Paciente chegou 10 min atrasado." → lida como `sem_acao`
  - Autorização vencida (bloqueia): Autorização AUT930138 venceu em 07/08/2026 e o atendimento foi em 21/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
- **G-2608-0050** · Centro · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 4 · R$ 70,00 · **R$ 70,00 em risco**
  - Autorização vencida (bloqueia): Autorização AUT864141 venceu em 03/08/2026 e o atendimento foi em 19/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
- **G-2608-0051** · Centro · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 6 · R$ 62,00 · **R$ 62,00 em risco**
  - Campo obrigatório vazio (bloqueia): Sem número da autorização. Saúde Interior exige. → Conseguir o número da autorização com o convênio antes de enviar. Sem ele, glosa.
- **G-2608-0056** · Centro · Plano Bem · Sessão de fisioterapia musculoesquelética · sessão 14 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Paciente chegou 10 min atrasado." → lida como `sem_acao`
  - Campo obrigatório vazio (bloqueia): Sem CID. Plano Bem exige. → Pedir o CID ao profissional que atendeu (está no pedido médico) e lançar antes de enviar.
  - Sessão acima do limite da autorização (bloqueia): Sessão nº 14 numa autorização que cobre 12. → Precisa de nova autorização. Plano Bem cobre 12 sessões por autorização.
- **G-2608-0057** · Sul · Vitalcard · Consulta ortopédica · sessão 7 · R$ 90,00 · **R$ 90,00 em risco**
  - Guia duplicada (bloqueia): Mesma carteirinha, data, procedimento, autorização e sessão da guia G-2608-0027. → Cancelar esta guia. A G-2608-0027 já cobre esse atendimento; enviar as duas é cobrança em dobro e glosa certa.
- **G-2608-0061** · Centro · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 8 · R$ 62,00 · **R$ 62,00 em risco**
  - Campo obrigatório vazio (bloqueia): Sem número da autorização. Saúde Interior exige. → Conseguir o número da autorização com o convênio antes de enviar. Sem ele, glosa.
- **G-2608-0063** · Sul · Plano Bem · Sessão de fisioterapia neurofuncional · sessão 4 · R$ 70,00 · **R$ 70,00 em risco**
  - Campo obrigatório vazio (bloqueia): Sem número da autorização. Plano Bem exige. → Conseguir o número da autorização com o convênio antes de enviar. Sem ele, glosa.
- **G-2608-0064** · Norte · Vitalcard · Sessão de fisioterapia musculoesquelética · sessão 12 · R$ 62,00 · **R$ 62,00 em risco**
  - Sessão acima do limite da autorização (bloqueia): Sessão nº 12 numa autorização que cobre 10. → Precisa de nova autorização. Vitalcard cobre 10 sessões por autorização. (Reavaliação médica obrigatória a cada 10 sessões; nova autorização a cada reavaliação.)
- **G-2608-0069** · Centro · Vitalcard · Consulta ortopédica · sessão 3 · R$ 90,00 · **R$ 90,00 em risco**
  - Observação da recepção: "Procedimento realizado foi drenagem linfática, lançar o código certo." → lida como `codigo_errado`
  - Código errado (observação) (bloqueia): Recepção anotou: 'Procedimento realizado foi drenagem linfática, lançar o código certo.'. Código lançado: 20103301 (Consulta ortopédica). → Trocar o código pelo procedimento realizado antes de enviar. 'drenagem linfática' não está na tabela dos convênios: provavelmente é particular.
- **G-2608-0072** · Centro · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 6 · R$ 62,00 · **R$ 62,00 em risco**
  - Autorização vencida (bloqueia): Autorização AUT459190 venceu em 10/08/2026 e o atendimento foi em 14/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
- **G-2608-0074** · Norte · Plano Bem · Reavaliação fisioterapêutica · sessão 12 · R$ 55,00 · **R$ 55,00 em risco**
  - Profissional incompatível com o procedimento (bloqueia): Reavaliação fisioterapêutica exige fisioterapeuta (CREFITO), mas o profissional lançado é Dr. Otávio Prado (CRM-SP 97731). → Ou o profissional está errado, ou o procedimento. Conferir com quem atendeu.
- **G-2608-0075** · Sul · Vitalcard · Consulta ortopédica · sessão 8 · R$ 90,00 · **R$ 90,00 em risco**
  - Autorização vencida (bloqueia): Autorização AUT567609 venceu em 11/08/2026 e o atendimento foi em 13/08/2026. Vai glosar. → Pedir nova autorização ao convênio antes de enviar.
- **G-2608-0076** · Sul · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 7 · R$ 70,00 · **R$ 70,00 em risco**
  - Guia duplicada (bloqueia): Mesma carteirinha, data, procedimento, autorização e sessão da guia G-2608-0059. → Cancelar esta guia. A G-2608-0059 já cobre esse atendimento; enviar as duas é cobrança em dobro e glosa certa.
- **G-2608-0077** · Norte · Plano Bem · Sessão de fisioterapia musculoesquelética · sessão 15 · R$ 62,00 · **R$ 62,00 em risco**
  - Sessão acima do limite da autorização (bloqueia): Sessão nº 15 numa autorização que cobre 12. → Precisa de nova autorização. Plano Bem cobre 12 sessões por autorização.

## Pendente: esperando algo com prazo (1)

- **G-2608-0041** · Centro · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 11 · R$ 62,00 · **R$ 62,00 em risco**
  - Observação da recepção: "Autorizado por telefone, protocolo 771203, aguardando número." → lida como `protocolo_verbal`
  - Autorização verbal aguardando número (pendente): Autorização verbal (protocolo 771203). Saúde Interior aceita por 5 dias úteis: até 27/08/2026. → Ligar no convênio, pegar o número da autorização e lançar até 27/08/2026. Não enviar antes disso.

## Corrigir: erro simples, conserta e envia (6)

- **G-2608-0013** · Norte · Vitalcard · Consulta ortopédica · sessão 2 · R$ 90,00 · **R$ 90,00 em risco**
  - Observação da recepção: "Confirmado pelo WhatsApp na véspera." → lida como `sem_acao`
  - Campo obrigatório vazio (corrigir): Sem registro do profissional. Vitalcard exige. → Preencher com o registro de Dr. Renato Albuquerque. Nas outras guias ele aparece como CRM-SP 84512.
- **G-2608-0016** · Centro · Saúde Interior · Sessão de fisioterapia musculoesquelética · sessão 17 · R$ 62,00
  - Formato de data ou valor (corrigir): Data do atendimento digitada como '03/08/2026'. O padrão do sistema é AAAA-MM-DD. → Corrigir a data do atendimento no sistema para 2026-08-03.
- **G-2608-0027** · Sul · Vitalcard · Consulta ortopédica · sessão 7 · R$ 90,00
  - Formato de data ou valor (corrigir): Data do atendimento digitada como '26/08/2026'. O padrão do sistema é AAAA-MM-DD. → Corrigir a data do atendimento no sistema para 2026-08-26.
- **G-2608-0030** · Sul · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 8 · R$ 70,00 · **R$ 70,00 em risco**
  - Observação da recepção: "Paciente trouxe autorização nova, número ainda não lançado. Validade 30/09." → lida como `nova_autorizacao`
  - Autorização vencida (corrigir): Autorização AUT297029 venceu em 17/08/2026 e o atendimento foi em 21/08/2026. A recepção anotou que o paciente trouxe autorização nova (validade 30/09), ainda não lançada. → Lançar o número e a validade da autorização nova e enviar.
- **G-2608-0033** · Centro · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 4 · R$ 70,00 · **R$ 70,00 em risco**
  - Campo obrigatório vazio (corrigir): Sem registro do profissional. Vitalcard exige. → Preencher com o registro de Felipe Andrade. Nas outras guias ele aparece como CREFITO-3 198302-F.
- **G-2608-0065** · Sul · Plano Bem · Sessão de fisioterapia musculoesquelética · sessão 5 · R$ 62,00
  - Formato de data ou valor (corrigir): Valor digitado como '62,00' (com vírgula). Li como 62.00. → Corrigir o valor no sistema para 62.00.

## Atenção: podem ir, mas alguém deveria olhar (5)

- **G-2608-0005** · Norte · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 10 · R$ 70,00
  - Observação da recepção: "Pediu recibo para reembolso do plano." → lida como `reembolso`
  - Pediu recibo pra reembolso (observação) (atencao): Recepção anotou: 'Pediu recibo para reembolso do plano.'. Reembolso é coisa de quem pagou particular. → Confirmar se essa guia vai mesmo pro Vitalcard ou se o paciente pagou direto.
- **G-2608-0015** · Centro · Vitalcard · Sessão de fisioterapia musculoesquelética · sessão 1 · R$ 62,00
  - Observação da recepção: "Pediu recibo para reembolso do plano." → lida como `reembolso`
  - Pediu recibo pra reembolso (observação) (atencao): Recepção anotou: 'Pediu recibo para reembolso do plano.'. Reembolso é coisa de quem pagou particular. → Confirmar se essa guia vai mesmo pro Vitalcard ou se o paciente pagou direto.
- **G-2608-0022** · Centro · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 2 · R$ 70,00
  - Observação da recepção: "Pediu recibo para reembolso do plano." → lida como `reembolso`
  - Pediu recibo pra reembolso (observação) (atencao): Recepção anotou: 'Pediu recibo para reembolso do plano.'. Reembolso é coisa de quem pagou particular. → Confirmar se essa guia vai mesmo pro Vitalcard ou se o paciente pagou direto.
- **G-2608-0034** · Sul · Vitalcard · Sessão de fisioterapia neurofuncional · sessão 3 · R$ 70,00
  - Observação da recepção: "Sessão remarcada de 12/08 para hoje, autorização era da data original." → lida como `remarcacao`
  - Sessão remarcada (observação) (atencao): Sessão remarcada. Autorização vale até 30/08/2026, cobre a nova data. → Nada a fazer.
- **G-2608-0066** · Norte · Vitalcard · Sessão de fisioterapia musculoesquelética · sessão 1 · R$ 62,00
  - Observação da recepção: "Pediu recibo para reembolso do plano." → lida como `reembolso`
  - Pediu recibo pra reembolso (observação) (atencao): Recepção anotou: 'Pediu recibo para reembolso do plano.'. Reembolso é coisa de quem pagou particular. → Confirmar se essa guia vai mesmo pro Vitalcard ou se o paciente pagou direto.

## OK: podem ir (36)

G-2608-0001, G-2608-0003, G-2608-0009, G-2608-0010, G-2608-0011, G-2608-0012, G-2608-0017, G-2608-0018, G-2608-0019, G-2608-0020, G-2608-0025, G-2608-0029, G-2608-0036, G-2608-0037, G-2608-0038, G-2608-0040, G-2608-0042, G-2608-0043, G-2608-0044, G-2608-0048, G-2608-0052, G-2608-0053, G-2608-0054, G-2608-0055, G-2608-0058, G-2608-0059, G-2608-0060, G-2608-0062, G-2608-0067, G-2608-0068, G-2608-0070, G-2608-0071, G-2608-0073, G-2608-0078, G-2608-0079, G-2608-0080
