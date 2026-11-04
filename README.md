# Mar Sudoeste v4.3 — atualização manual pelo ChatGPT

Aplicação web/PWA para **surfcasting, surf, spinning, caça submarina e ir à maré**, entre Costa de Santo André e Vila Nova de Milfontes.

A v4.3 consolida a v4.2 e substitui a atualização automática de APIs no navegador pelo processo **ChatGPT → forecast.json → Importar atualização IA**. **Não requer OpenAI API, API key nem subscrição de serviços adicionais** além dos meios que o utilizador já utiliza. Os limites de utilização habituais do ChatGPT continuam a aplicar-se.

## Como instalar no GitHub Pages

1. Descompactar o ZIP e colocar **o conteúdo da pasta**, incluindo `index.html`, na raiz de `duartejlino/surfcasting-sudoeste` (`main`). Substituir versões antigas dos ficheiros quando necessário.
2. Confirmar **Settings → Pages → Deploy from a branch → main → /(root)**.
3. Abrir `https://duartejlino.github.io/surfcasting-sudoeste/` após o deploy.
4. Atualizar/reabrir a app no telemóvel para ativar o novo service worker (`mar-sudoeste-v4-3-manual`).

**NOTA SOBRE O FORECAST EMBUTIDO:** o `data/forecast.json` incluído no ZIP é o anterior, gerado a **2026-11-03T14:45:00+00:00**, para **3–9 novembro**. **Não foi atualizado ao criar esta v4.3.** A app mostra a data de geração, assinala quando a previsão tem mais de 36 h e nunca faz uma nova previsão por si. Para obter uma previsão recente, pedir explicitamente uma atualização ao ChatGPT e importar o JSON.

## Como atualizar, sem GitHub

1. Pedir no chat: **«Atualiza o Mar Sudoeste para os próximos 16 dias, com as cinco atividades e auditoria das fontes»**.
2. Descarregar o `forecast.json` fornecido pelo ChatGPT. O horizonte real pode ser inferior a 16 dias se não houver dados verificáveis.
3. No site, carregar em **Importar atualização IA** (ou **Importar forecast.json**) e escolher o ficheiro.
4. Confirmar a data de geração e as notas em **Atividades → Calendário / Raciocínio**.

O JSON fica guardado **nesse navegador/dispositivo**, comprimido quando suportado. **Não é enviado para o GitHub nem sincronizado entre aparelhos.** Podes importar o mesmo ficheiro noutro telemóvel. Um deploy do site não altera o histórico guardado nesse navegador; é aconselhável exportar cópias periódicas.

## Aprendizagem com saídas reais

Em **Histórico**, registar a atividade, praia, período, capturas/avistamentos, isco, avaliação e notas de campo. O registo guarda também a previsão existente nessa sessão. Carregar em **Exportar histórico para ChatGPT** e enviar o JSON nesta conversa. O ChatGPT pode comparar previsões e resultados e produzir novo `forecast.json` com ajustes identificados e prudentes. **A app não comunica o histórico ao ChatGPT automaticamente.**

## Diferença entre notas IA e notas antigas

- `evaluations`: a avaliação explicada de surfcasting (quatro espécies, seis períodos, praias elegíveis) já calculada no `forecast.json`.
- `activity_evaluations`: **opcional** no formato antigo, mas recomendado/esperado nas próximas análises manuais. Contém notas e explicações **pré-calculadas no ChatGPT** para surf, spinning, caça submarina e ir à maré, incluindo níveis de surf.
- Se `activity_evaluations` existir e tiver registos, o site apresenta os registos que lá estão e **não recalcula essas notas**. Ausências ficam sem avaliação.
- O forecast antigo incluído neste ZIP não contém `activity_evaluations`. Para garantir compatibilidade, a app ainda usa as **fórmulas locais provisórias** da v4.2 para estas quatro atividades, identificando-as claramente na interface. **Não são previsões IA atualizadas.**

## Regras permanentes

- Samoqueira **excluída apenas de surfcasting**, por preferência do utilizador. Pode ser analisada nas outras atividades **se forem apropriadas e legais**.
- Marés oficiais do **Instituto Hidrográfico para Sines, novembro de 2026**, incluem horário, altura referida ao zero hidrográfico e amplitude da preia-mar/baixa-mar adjacente. Fora desse mês a altura oficial não está integrada nesta versão.
- O local concreto dos bancos, a visibilidade subaquática, a existência de rochas seguras, o caudal da foz do Mira e a autorização de captura **não são observados automaticamente**.
- Caça submarina/«ir à maré»: previsões ambientais não são autorização legal nem certificação de segurança. Confirmar licenciamento, espécies, períodos, zonas protegidas e acessos no terreno.
- A **confiança é um indicador heurístico sobre a evidência e os modelos**, não probabilidade estatisticamente calibrada.

## Fontes e rastreabilidade

O ChatGPT deverá usar o máximo de fontes verificáveis pertinentes: Instituto Hidrográfico, IPMA, previsões oceanográficas por coordenada/modelo (ex. Open-Meteo com centros NOAA, ECMWF, DWD quando efetivamente acessíveis), observações e previsões locais relevantes. Não contar websites que mostrem o mesmo modelo como previsões independentes. Registar `source_registry`, `source_failures` e `source_audit` para cada avaliação quando a fonte foi de facto consultada. Não preencher valores ausentes por invenção e diferenciar **previsão local direta / modelo na coordenada / regional ajustado**.

A consulta das fontes e a criação do novo ficheiro ocorrem **apenas quando o utilizador o pede no ChatGPT**, não na app nem em automações agendadas.

Consulta [COMO_ATUALIZAR.md](COMO_ATUALIZAR.md) e [AI_UPDATE_SPEC.md](AI_UPDATE_SPEC.md).
