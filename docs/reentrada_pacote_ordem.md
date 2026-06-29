# Pacote `/ordem` — Saída Flat + Reentrada + N Estratégias (V2.6)

> Este documento é a **especificação da reconciliação per-cliente** que vive no repo
> **iavest-trade** (a rota `POST /claude-trader/ordem`). O lado do **cérebro** (abrir a op
> de reentrada) e o **banco** já estão feitos no iavest-backend. Aqui está o que falta no
> consumidor.

## O que já foi feito (iavest-backend + banco)
- `claude_trader_operacao.origem ENUM('principal','reentrada')` — criada (default `principal`).
- `claude_trader_mt5_ordens.acao` — ganhou o valor `'encerrar_flat'`.
- Cérebro: com `reentrada=True` (config por estratégia), abre uma op paralela
  `origem='reentrada'` quando há principal aberta + sinal forte fresco na **mesma direção**.
- **Prod (id=6) está com `reentrada=False`** → nada muda lá até a gente ligar num id de teste.

## Contrato do EA — NÃO MUDA
O EA continua mandando o mesmo payload. O campo que destrava tudo já existe:
```json
{ "account_number":"...", "id_estrategia":6,
  "tem_posicao_aberta":false, "tipo_posicao_mt5":null, "posicao_atual":0, "password":"..." }
```

---

## Conceitos

- **Guia** = ops em `claude_trader_operacao` da estratégia (`WHERE id_estrategia=X AND status='aberta'`).
  Pode haver **principal** e **reentrada** (no máx. 1 de cada).
- **Entrega** = linha em `claude_trader_mt5_ordens` (`account_number`, `id_operacao`, `id_estrategia`, `acao`, `status`).
  É o histórico do que mandamos pra **aquele cliente** sobre **aquela op**.
- **`flat_desde`** = quando o cliente ficou sem posição. Use o `created_at` da última entrega
  `encerrada` dele (ou o primeiro poll, se nunca operou). Serve pra **não perseguir op em andamento**.

**Tudo é filtrado por `id_estrategia`** → atende 1 ou N estratégias sem acoplamento. Se um cliente
assina N estratégias, o EA chama uma vez por `id_estrategia`, e a reconciliação roda isolada por estratégia.

---

## Algoritmo da reconciliação (por poll, por cliente, por estratégia)

```
ordem(account, id_estrategia, tem_posicao, tipo_mt5, preco):

    principal = guia_aberta(id_estrategia, origem='principal')   # ou None
    reentrada = guia_aberta(id_estrategia, origem='reentrada')   # ou None
    entrega   = ultima_entrega_aberta(account, id_estrategia)    # row mt5_ordens status='aberta' (ou None)
    op_atual  = op_da_entrega(entrega)                           # a op que ele espelha hoje

    # ---------------- CLIENTE COM POSIÇÃO ----------------
    if tem_posicao:
        if op_atual is None or op_atual.status == 'encerrada':
            # a guia encerrou (stop/alvo/flip/eod) mas o cliente ainda está dentro → fecha
            marca_entrega(entrega, status='encerrada', acao='encerrar')
            return resposta('encerrar', motivo=op_atual.motivo)
        if op_atual.stop_loss != entrega.stop_loss:
            # a proteção subiu o stop → propaga
            atualiza_entrega(entrega, stop_loss=op_atual.stop_loss, acao='mover_stop')
            return resposta('mover_stop', stop=op_atual.stop_loss)
        return resposta('manter')

    # ---------------- CLIENTE FLAT ----------------
    # 1) ele tinha entrega aberta e agora está flat → registrar a SAÍDA
    if entrega and entrega.status == 'aberta':
        if op_atual and op_atual.status == 'encerrada':
            # saída pela GUIA (stop/alvo/flip/eod) — encerramento normal
            marca_entrega(entrega, status='encerrada', acao='encerrar')
        else:
            # guia ainda ABERTA, mas o cliente está flat → SAÍDA FLAT (manual)
            marca_entrega(entrega, status='encerrada', acao='encerrar_flat',
                          motivo='saída manual detectada (reconciliação)')
        flat_desde = agora()        # ele acabou de ficar flat

    flat_desde = flat_desde or ultima_saida(account, id_estrategia) or agora()

    # 2) candidata a (re)entrada: op que ele AINDA NÃO operou e que nasceu DEPOIS de ele ficar flat
    #    (reentrada tem prioridade — é a entrada fresca; depois a principal)
    for cand in [reentrada, principal]:
        if cand is None:                      continue
        if ja_tem_entrega(account, cand):     continue   # TRAVA anti-perseguição (por id_operacao)
        if cand.abertura_em < flat_desde:     continue   # NÃO persegue op em andamento (login atrasado)
        registra_entrega(account, id_estrategia, cand, acao='abrir',
                         stop=cand.stop_loss, gain=cand.stop_gain)
        return resposta('abrir', op=cand)

    return resposta('aguardar')   # nada novo — fica de fora
```

### As 3 regras que resolvem os 3 desafios

| Desafio | Linha do algoritmo |
|---|---|
| **Saída flat** | `acao='encerrar_flat'` quando `guia aberta + cliente flat` (divergência) |
| **Reentrada** | candidata `reentrada` (id_operacao NOVO) → `ja_tem_entrega` é False → entrega `abrir` |
| **N estratégias** | tudo filtrado por `id_estrategia` |

### Por que `cand.abertura_em < flat_desde` é importante
É o que diferencia **"entrada fresca"** de **"perseguir o trade em andamento"**:
- Cliente saiu/logou **antes** da reentrada nascer → `reentrada.abertura_em >= flat_desde` → **pega**. ✅
- Cliente logou **atrasado** (depois da principal abrir) → `principal.abertura_em < flat_desde` → **não persegue**, espera a próxima op fresca. ✅

### Isolamento (quem está dentro não é afetado)
- Cliente com `tem_posicao=true` cai no ramo de cima → só espelha a op_atual dele (a principal).
  Ele **nunca** recebe a reentrada, porque a candidata só é avaliada no ramo flat.

---

## Resposta ao EA
Vocabulário idêntico (`abrir/manter/mover_stop/encerrar`). Para "não faça nada", reusar `manter`
ou adicionar `aguardar` na resposta (não precisa no enum do banco — é só payload de saída).

## Rollout seguro
1. Banco + cérebro (feito; reentrada OFF em prod).
2. Deploy do `/ordem` com este algoritmo no iavest-trade.
3. Criar **estratégia de teste** (ex.: id=8) com `parametros={"reentrada":true}` e apontar 1 conta de teste.
4. Validar em pregão. Só depois (se quiser) ligar `reentrada` no id=6.
```
