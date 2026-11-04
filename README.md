# Mar Sudoeste v4.5 · Filtro global e catálogo ampliado

A v4.4 usa **um seletor global no topo**: Surfcasting, Surf, Pesca spinning, Caça submarina e Ir à maré. A escolha governa **Resumo, Calendário diário/mensal, Comparação de praias, Raciocínio, Praias, Histórico, Aprendizagem e pesos no Modelo**.

## Pesquisa local

O ficheiro `PESQUISA_LOCAIS_ATIVIDADES.md` reúne leituras para as sete zonas × cinco atividades, com ligações a Turismo de Portugal, guias locais e DGRM/IPMA. No separador **Praias**, cada atividade tem recomendações específicas e fontes clicáveis. **Os factos geográficos são separados das interpretações de atividade**: não atribuímos capturas, visibilidade medida, nem permissão legal sem dados.

A Samoqueira continua **excluída apenas do surfcasting**. A lista de zonas é específica da atividade e inclui apenas locais suficientemente caracterizados; uma zona omitida não é automaticamente proibida.

## Modo sem custos de API

O site não usa OpenAI API. Os novos `forecast.json` são gerados no chat quando o utilizador pede e carregados através de **Importar atualização IA**. Os antigos continuam compatíveis. O histórico fica apenas no navegador e pode ser exportado/importado.

O ficheiro fornecido é o anterior, gerado em novembro de 2026, e é **antigo para decisões futuras**. Quando não há `activity_evaluations` pré-calculadas no JSON, **Surf, Spinning, Caça submarina e Ir à maré mostram explicitamente fórmulas locais provisórias**, com fatores e limitações. Não são falsamente apresentados como análises IA validadas. Os próximos forecasts devem incluir notas explicadas por atividade, seguindo `AI_UPDATE_SPEC.md`.

## Segurança e limites

- Caça submarina: não é efetuada à noite, necessidade de boia, licença e área permitida; visibilidade real e corrente devem ser verificadas.
- Ir à maré: a altura e amplitude astronómicas de Sines são dados regionais, não certificam acesso a plataformas nem recolha de espécies. Confirmar interdições, espécies e licenciamento.
- Surf: onda offshore não é igual à onda que rebenta; o nível é um filtro de conforto, nunca uma garantia.
- O site não substitui observação na praia, DGRM, IPMA ou Capitania.

## Publicação

Enviar `index.html`, `app.js`, `styles.css`, `sw.js`, `manifest.webmanifest` para a raiz do GitHub Pages (os ficheiros `data/` podem ser conservados). O ZIP completo inclui também guia, fontes e verificador de forecasts. Atualizações IA futuras **não** precisam de novo upload de código para GitHub.

## Melhoria v4.4.1 — guias dos spots

As fichas de São Torpes, Praia Grande Porto Covo, Aivados e Malhão passaram a incluir **descrições locais recolhidas em Surfnerd, Surfline e outros guias de surf**, visíveis em **Praias** para todas as atividades, com links diretos e interpretação assinalada. O `forecast.json` importado continua a controlar as notas. Esta atualização não mexe no histórico, nas regras de elegibilidade nem nos dados preexistentes. Ver `FONTES_SURF_SPOTS_2026-11.md`.

## v4.5 · Spots adicionais

Foram adicionadas 7 zonas com coordenadas, guias por atividade e fontes: Areão, Morgavel, Vieirinha, Burrinho, Ilha do Pessegueiro, Patacho e Farol de Milfontes. As praias novas aparecem nas listas de atividades elegíveis, **marcadas sem previsão própria**, sem notas inventadas. Consultar `NOVAS_PRAIAS_E_FONTES.md`.

A ferramenta opcional `tools/Recolher_Dados_Mar_Sudoeste_14_Zonas.html` recolhe séries por coordenada para as 14 zonas, para enviares nesta conversa e gerar o próximo `forecast.json`. Não é preciso instalar API paga. Para recolha automática no GitHub, substituir `scripts/collect_sources.py` pelo ficheiro `tools/collect_sources_14_spots.py` (o workflow existente continua a chamar o mesmo caminho).

**Instalação:** usar o ZIP completo. Enviar `spot_catalog.js` juntamente com `app.js`/`index.html`; o novo service worker está incluído. **Não é preciso importar outro forecast só para consultar as fichas**.
