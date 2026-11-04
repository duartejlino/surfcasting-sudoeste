# Mar Sudoeste v4.6 — Radar de oportunidades

## O que mudou

- O antigo separador Calendário chama-se **Oportunidades**.
- Vista inicial **Linha temporal**: gráfico de 15 dias no desktop; lista diária compacta no telemóvel; seleção revela o melhor trio de praias e respetiva justificação.
- **Praias × dias**: matriz comparativa com pontuação e confiança de cada praia e dia, incluindo detalhe ao clicar.
- As vistas **Detalhe por horas** (seis períodos) e **Calendário mensal** foram conservadas.
- Layout em largura total no computador, sem estreitamento artificial a 1180 px.
- O filtro global de atividade, o filtro de espécie no surfcasting, o nível de surf, as restrições, o histórico e a importação de JSON mantêm-se.
- Nenhum cálculo novo de meteorologia ou previsão: apenas visualização das avaliações que o ChatGPT enviou e que já estão na aplicação.

## Notas importantes

- A cor representa apenas o **valor de pontuação** e não segurança, licença nem probabilidade real.
- Avaliações de risco ou sem pontuação ficam **sem nota validada** e nunca são exibidas como verdes.
- A confiança é heurística e apresentada à parte; na maré/caça submarina não substitui verificação de visibilidade, correntes ou autorização.
- Na vista rápida apenas se escolhe a melhor janela de cada dia; as seis janelas encontram-se em Detalhe por horas.
- Mantém compatibilidade com o `forecast.json` de 14 zonas / 4–18 novembro 2026 e com o histórico já guardado no browser.

## Instalação

Enviar o conteúdo do ZIP completo à raiz do repositório GitHub Pages. Se a v4.5 já estiver instalada, basta substituir `index.html`, `app.js`, `styles.css` e `sw.js`.
