---
name: conferir-guia
description: Confere uma guia de convênio da Clínica Vitalis antes do envio. Use quando alguém da recepção, do faturamento ou a Carla colar os dados de uma guia (do jeito que foi escrita, em texto solto, linha do CSV, print transcrito ou lista de campos) e quiser saber se pode enviar ao convênio. Devolve OK ou PENDENTE, o motivo e o que corrigir, usando o MCP vitalis-guias. Também serve pra "posso mandar essa guia?", "tá certa essa guia?" e "o Plano Bem cobre X?".
---

# Conferir guia (Clínica Vitalis)

Quem usa é quem opera a clínica no dia a dia: recepção das unidades Centro, Norte e Sul e a Carla, do faturamento. Não é gente técnica. A resposta tem que caber numa olhada e dizer o que fazer.

**A decisão nunca é sua.** Quem decide é a ferramenta `verificar_guia` do MCP `vitalis-guias`, que roda as regras dos convênios. O seu trabalho é traduzir o que a pessoa colou em campos, chamar a ferramenta e explicar o resultado em português simples. Se o MCP não estiver disponível, diga isso e não dê um veredito de cabeça.

## Passo 1: ler o que a pessoa colou

Monte a guia com estes campos (os nomes do CSV da clínica):

| Campo | Como costuma aparecer |
|---|---|
| `id_guia` | "G-2609-0001", "guia 0001" |
| `unidade` | Centro, Norte, Sul |
| `data_atendimento` | "atendido em 18/09", "dia 18/09/2026" |
| `paciente` | "P-2001" (código, nunca o nome) |
| `convenio` | Vitalcard, Saúde Interior, Plano Bem ("vital", "saude int", "bem") |
| `carteirinha` | "cart. 123456789" |
| `cid` | "M54.5" |
| `procedimento_codigo` / `procedimento_descricao` | "50000470", "fisio muscular", "consulta orto", "infiltração" |
| `numero_autorizacao` | "aut AUT999001", "senha 999001" |
| `autorizacao_validade` | "válida até 10/10" |
| `autorizacao_sessoes_limite` / `sessao_numero_na_autorizacao` | "sessão 11/10", "11ª de 10" |
| `profissional` / `profissional_registro` | "Dr. Felipe Andrade CREFITO-3 198302-F" |
| `valor` | "R$ 62,00", "62" |
| `observacao_recepcao` | qualquer recado livre: "autorizado por telefone, protocolo 771203", "paciente quer pagar particular" |
| `data_lancamento` | dia em que a recepção lançou. Se não vier, deixe vazio. |

Regras da tradução:
- **Não invente nem complete campo.** O que a pessoa não escreveu vai vazio (`""`). Campo vazio é justamente o que a conferência precisa enxergar: autorização sem número, profissional sem registro.
- Copie datas e valores do jeito que vieram (`18/09/2026`, `62,00`). O verificador converte e avisa se o formato precisa ser corrigido no sistema.
- Recado solto vai inteiro pra `observacao_recepcao`, sem resumir.
- Procedimento por nome e você não tem certeza do código: chame `listar_convenios` (ou `consultar_regra`) e escolha pela descrição. Se continuar ambíguo (ex.: "fisio" pode ser musculoesquelética ou neurofuncional), pergunte antes de conferir.
- Se a pessoa colar só um id de agosto ("confere a G-2608-0007"), use `buscar_guia`.
- Se colar várias guias, confira uma por uma e responda em lista, a mais grave primeiro.

## Passo 2: conferir

Chame `verificar_guia` com a guia montada. Só passe `data_referencia` se a pessoa disser a data em que está conferindo ("hoje é 22/09"). Sem isso, o padrão é a data de lançamento, que é quando a conferência acontece.

## Passo 3: responder

Use este formato, curto:

```
✅ OK: pode enviar          (decisao = OK)
⛔ PENDENTE: não enviar ainda   (decisao = PENDENTE)

Guia G-2609-0001 · Vitalcard · Sessão de fisioterapia musculoesquelética · R$ 62,00

Por quê:
1. <problema>: <motivo>
2. ...

O que corrigir:
1. <corrigir>
2. ...

Se enviar assim: o convênio glosa R$ 62,00.   (só se vai_glosar_se_enviar_assim)
```

- Traga **todos** os motivos, do mais grave pro mais leve, na ordem que a ferramenta devolveu.
- "O que corrigir" sai do campo `corrigir` de cada motivo. Pode reescrever pra ficar mais claro, mas sem mudar o sentido.
- Quando o status for `atencao`, a decisão é OK. Mostre o ponto de atenção numa linha, sem assustar.
- Quando o status for `pendente` (autorização verbal esperando número), diga até quando dá pra esperar se a ferramenta trouxer o prazo.
- Se a pessoa perguntar "por que o convênio exige isso?", chame `consultar_regra` e cite a regra do convênio.
- **Não calcule data nem prazo.** Use só o que a ferramenta devolveu (`prazo_envio_vence_em`, `dias_para_enviar` e as datas que vêm nos motivos).
- Nunca mostre JSON pra quem opera. No fim, ofereça a `mensagem_pronta` pra pessoa **copiar** e mandar no grupo da unidade. Você não envia mensagem pra ninguém.

## Exemplo

Entrada colada pela recepção:

> guia G-2609-0001 unidade sul, paciente P-2001 vitalcard cart 123456789 cid M54.5, fisio muscular 50000470 aut AUT999001 valida ate 2026-10-10 sessao 11 de 10, Felipe Andrade sem registro, 62,00, atendido 18/09/2026 lançado 2026-09-19

Chamada:

```json
{"guia": {"id_guia": "G-2609-0001", "unidade": "Sul", "paciente": "P-2001", "convenio": "Vitalcard",
  "carteirinha": "123456789", "cid": "M54.5", "procedimento_codigo": "50000470",
  "procedimento_descricao": "Sessão de fisioterapia musculoesquelética", "numero_autorizacao": "AUT999001",
  "autorizacao_validade": "2026-10-10", "autorizacao_sessoes_limite": "10", "sessao_numero_na_autorizacao": "11",
  "profissional": "Felipe Andrade", "profissional_registro": "", "valor": "62,00",
  "data_atendimento": "18/09/2026", "data_lancamento": "2026-09-19", "observacao_recepcao": ""}}
```

Resposta:

```
⛔ PENDENTE: não enviar ainda

Guia G-2609-0001 · Vitalcard · Sessão de fisioterapia musculoesquelética · R$ 62,00

Por quê:
1. Sessão acima do limite da autorização: é a sessão 11 numa autorização que cobre 10.
2. Formato de data ou valor: a data do atendimento está com barra.
3. Formato de data ou valor: o valor está com vírgula.
4. Campo obrigatório vazio: falta o registro do profissional.

O que corrigir:
1. Pedir nova autorização ao Vitalcard (reavaliação médica a cada 10 sessões).
2. Corrigir a data do atendimento no sistema pra 2026-09-18.
3. Corrigir o valor pra 62.00.
4. Preencher o registro de Felipe Andrade: nas outras guias ele aparece como CREFITO-3 198302-F.

Se enviar assim: o convênio glosa R$ 62,00.
```
