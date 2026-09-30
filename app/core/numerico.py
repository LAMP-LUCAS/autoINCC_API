"""
Tipo numérico de fronteira — ADR 009 (JSON number).

`Decimal` é o tipo correto para **cálculo** (fator de correção, índice oficial,
CUB/m²): ponto flutuante binário acumula erro onde dinheiro e índice não podem.
O problema é a **serialização**: o Pydantic v2 converte `Decimal` em `str` por
padrão, então a API entregava `"valor_corrigido": "266519.20"` — texto que o
agente, a planilha e qualquer cliente tipado precisam parsear antes de somar.

A solução é um único tipo anotado: `Decimal` continua no domínio e vira `float`
**só** na saída JSON.

    Num = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]

Regras (ADR 009):
1. Cálculo permanece em `Decimal` — este tipo é usado **apenas** em schemas de
   RESPOSTA, nunca em coluna de banco nem em regra de negócio.
2. Datas continuam string ISO (`date`/`datetime` do Pydantic) — inalterado.
3. Precisão: `float` tem ~15–17 dígitos significativos; o consumidor é
   humano/agente/planilha, não replicador contábil. Quem precisar de precisão
   exata usa a fonte (SGS) ou o banco.
4. O cache usa `model_dump(mode="json")` — a mudança vale para o cache junto
   (exige flush das camadas na ativação).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

Num = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float, when_used="json"),
]
