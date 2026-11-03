# Contrato de atualização pela IA

O ficheiro `data/forecast.json` é a fronteira entre o motor de análise e a app.

## Regras

- `schema_version` deve ser `3`.
- Cada combinação relevante deve existir em `evaluations`.
- Uma avaliação tem `date`, `beach_id`, `period`, `species`, `score`, `confidence`, `summary`, `why_not_10`, `factors`, `sensitivities` e `conditions`.
- `score` é 0–10.
- `confidence` é 0–100 e mede qualidade/concordância dos dados, não qualidade da pesca.
- Cada fator contém `score`, `weight`, `impact`, `reason`, `source` e `confidence`.
- Os pesos de todos os fatores devem somar 1,00.
- Nenhuma alteração de pesos deve ser silenciosa: a atualização deve explicar por que mudou e manter registo na análise.

## Histórico para recalibração

A app exporta `surfcasting_historico_para_chatgpt.json`. O motor deve:

1. comparar previsão e avaliação real;
2. segmentar por praia, período, espécie e condições;
3. evitar conclusões fortes com amostras pequenas;
4. aplicar shrinkage / regularização às correções;
5. distinguir ausência de capturas de ausência de atividade (toques);
6. preservar explicabilidade: qualquer correção pessoal deve aparecer como fator/ajuste identificável.
