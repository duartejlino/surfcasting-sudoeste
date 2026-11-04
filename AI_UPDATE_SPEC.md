# Contrato da atualização manual ChatGPT → Mar Sudoeste v4.4

## Ficheiro

- JSON UTF-8 (`forecast.json`), `schema_version`: `3`, `generated_at` ISO 8601 com fuso.
- `area`, `generator` e notas de limitações/intervalo de previsão.
- `beaches`: dicionário de locais com IDs imutáveis, coordenadas e descrições.
- `evaluations`: resultados **pré-calculados** para surfcasting, cada objeto com `date` ISO, `beach_id`, `period`, `species` (Geral, Robalo, Sargo, Dourada), `window`, `score` (0–10), `confidence` (0–100), `summary`, `why_not_10`, `conditions`, `factors` e `sensitivities`. Cada fator deve ter `id`, `label`, `value`, `unit`, `score`, `weight`, `impact`, `source`, `confidence` e `reason`. A soma dos pesos = 1, salvo ajuste explicitamente declarado e contabilizado.
- `activity_evaluations`: lista de resultados pré-calculados **para surf, spinning, caça submarina e ir à maré**. Não incluir surfcasting aqui, pois já usa `evaluations`. A chave lógica é `(date, activity, beach_id, period, surf_level se activity=surf)`. Para surf gerar os níveis `iniciante`, `intermedio`, `experiente`. Cada objeto contém pelo menos:

```json
{
  "date": "2026-11-05",
  "activity": "spinning",
  "beach_id": "aivados",
  "period": "Amanhecer",
  "window": "06:30–08:20",
  "score": 7.6,
  "potential": 7.6,
  "confidence": 64,
  "status": "Potencial ambiental condicionado",
  "risky": false,
  "observation": "Mar e vento modelados, não observados no local",
  "origin": "modelo na coordenada",
  "source": "Centros/modelos efetivamente consultados",
  "reasons": ["Porque esta combinação pode favorecer a atividade"],
  "limits": ["Acesso, condições reais e restrições por confirmar"],
  "factors": [
    {"name":"Altura da onda", "value":0.8,"unit":"m", "score":8.3,"weight":0.25,"impact":2.075,"reason":"Critério explicado e sua origem"}
  ]
}
```

O exemplo mostra **formato, não uma previsão observada**. A app lê `activity_evaluations` diretamente: não recalcula o score ali. Se faltarem avaliações num ficheiro com `activity_evaluations`, não fabrica as células ausentes. O ficheiro antigo incluído na instalação não tem este campo e ativa temporariamente uma fórmula local **expressamente identificada como provisória**.

## Auditoria das fontes

- `source_registry`: consultas verdadeiramente realizadas, campos `requested_at` (hora da consulta), centro/modelo, endpoint/origem, coordenadas, período e resolução aplicável.
- `source_failures`: fontes indisponíveis, respostas não obtidas ou variáveis em falta.
- `evaluations[].source_audit`: valores **reais capturados** de cada fonte para o período selecionado, mediana/consenso quando comparáveis, dispersão e diferença para a fonte oficial. A fonte diária IPMA pode ser validação regional, mas **não pode ser tratada como medição horária independente**.
- `factors[].evidence`: evidência por fator, com fonte, horário, variável e valor quando comprovadamente existente.
- O mesmo centro republicado por vários websites **conta uma única vez** no consenso. Período médio, de pico e de swell não são diretamente equivalentes.
- Não rotular extrapolação regional como medição de praia, nem usar um modelo afastado como observação local.

## Marés e atividades

- Considerar a Tabela de Marés de Sines, com altitude referida ao **zero hidrográfico**, horários e diferença de altura entre extrema adjacentes (amplitude). Não usar uma tabela MSL como se fosse zero hidrográfico.
- Não atribuir nota definitiva quando faltam dados críticos de segurança; diferenciar potencial ambiental de condições seguras.
- `samoqueira`: excluída de **surfcasting**; elegível para spinning, caça submarina e ir à maré, mas com acesso e restrições ainda a verificar; surf não classificado se não houver evidência de spot surfável.
- Baixa-mar grande não significa rochas seguras. Caça submarina depende de visibilidade real, corrente, janela diurna e licenças. Apanha depende da espécie e das regras em vigor, inclusive áreas protegidas.
- Não extrapolar mar/vento para além do horizonte real das fontes. Meses sem marés IH verificadas não recebem classificações de apanha fundamentadas em altura oficial.

## Aprendizagem

Usar o histórico JSON exportado da app para comparar previsões e realidade. Corrigir erros com regularização para amostras pequenas e distinguir diferenças por atividade, praia, período e espécie. Mostrar os ajustes explicitamente; não esconder alterações de pesos/versões.

## Validação antes da entrega

Confirmar compatibilidade do JSON, intervalo dos scores, fuso, duplicados de `(data, praia, período, espécie/atividade, nível)`, pesos, valores em falta, frescura das fontes e todas as zonas elegíveis. Fornecer JSON diretamente descarregável para **Importar atualização IA**.

## Filtro global e investigação por local

O site apresenta uma única atividade de cada vez: Resumo, Calendário dia/mês, Comparação, Raciocínio, Praias, Histórico, Aprendizagem e Modelo. A lista de zonas é definida por atividade: não confundir exclusão por preferência/ausência de caracterização com interdição legal.

As novas avaliações devem usar as hipóteses do ficheiro `PESQUISA_LOCAIS_ATIVIDADES.md` **apenas como contexto/priors**, nunca como medições de peixe, visibilidade, corrente na rocha ou capturas. Se uma hipótese afetar a nota, registar esse impacto como critério explícito, com fonte e incerteza.

Fontes públicas de geografia local: Turismo de Portugal e guias locais; restrições DGRM, bivalves IPMA. Para qualquer captura/apneia, confirmar regras e área exata (PNSACV), nunca inferir autorização de uma previsão meteorológica.
