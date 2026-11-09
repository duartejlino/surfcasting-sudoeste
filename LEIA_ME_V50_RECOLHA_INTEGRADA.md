# Mar Sudoeste v5.0 — Recolha meteorológica integrada

A partir desta versão existe um separador **Atualizar dados** (ao lado de Oportunidades) com o recolhedor das 14 zonas, incorporado no site. Não precisas de abrir nem instalar um HTML separado no Android. No Resumo existe um atalho **Recolher dados novos**.

## Passos

1. Abrir **Atualizar dados** → **Recolher dados agora**. Acompanhar 90 consultas (4 modelos marítimos + meteorologia + extras, 3 estações de chuva e 3 produtos diários IPMA). A recolha só acontece quando se clica no botão, sem atualização automática. Mantém a página aberta.
2. Descarregar **Mar_Sudoeste_FONTES_AAAA-MM-DD.json**. Enviar o ficheiro ao ChatGPT com «Atualiza o Mar Sudoeste com estas fontes».
3. Quando tiveres o **forecast.json** gerado pelo ChatGPT, usar **Importar forecast calculado** na mesma página para atualizar as notas.

### O que muda / não muda

- A página consulta as APIs gratuitas da Open-Meteo e do IPMA diretamente, do dispositivo do utilizador, sem servidor adicional e sem credenciais. As APIs podem falhar ou limitar pedidos; isso é reportado por fonte. O motor conserva as estratégias de fallback para variáveis marítimas não suportadas.
- **Dados brutos não são notas**: o recolhedor exporta o formato de fontes `mar-sudoeste-browser-source-snapshot-v1`; importar isto em «forecast.json» não é válido.
- **Não há atualização automática** nem análise IA dentro da aplicação: o ChatGPT continua a gerar a previsão com as notas e auditoria. Nenhum resultado é anunciado como atualizado sem importar esse forecast.
- Durante a recolha, o JSON fica apenas na memória do browser e pode ser descarregado; não é enviado a um servidor próprio. Não existem medições diretas de turbidez, macroalgas ou visibilidade subaquática.
- A v4.9 com Água e algas, os bloqueios de segurança, o histórico e a calibração de surf mantêm-se.

### Instalação

**Site completo**: carregar os ficheiros do ZIP na raiz do repositório GitHub Pages. **Patch da v4.9**: substituir `index.html`, `styles.css`, `sw.js` e adicionar `collector.js` e este README. Atualizar/reabrir a PWA para renovar a cache.

**Testes:** validação JavaScript e interface em navegador com respostas simuladas das APIs; a recolha real depende da disponibilidade dos serviços e de permissões CORS.
