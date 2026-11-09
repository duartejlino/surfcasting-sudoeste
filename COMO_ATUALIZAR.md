# v5.0 — Recolher fontes dentro do site

1. Abrir o separador **Atualizar dados**, carregar **Recolher dados agora** e descarregar o JSON de fontes.
2. Enviar o JSON ao ChatGPT nesta conversa e pedir novo forecast.
3. Na aplicação, importar o forecast IA calculado. As notas não mudam apenas por recolher dados brutos.

# Atualizações manuais do Mar Sudoeste

## Um pedido basta

Na conversa onde desenvolvemos o Mar Sudoeste, escreve:

> Atualiza o Mar Sudoeste. Quero previsões para os próximos dias, idealmente até 16, para todas as atividades e praias elegíveis, com notas fator a fator, alturas/amplitudes oficiais das marés, comparação de modelos, divergências, fontes e justificação prática. Não inventes valores se uma fonte falhar. Devolve um forecast.json que possa importar diretamente na app.

Se já registaste saídas, anexa o ficheiro que descarregaste em **Histórico → Exportar histórico para ChatGPT**.

## Importar no site

- Abre o site no browser onde tens o histórico.
- Toca em **Importar atualização IA**.
- Escolhe o novo ficheiro `.json`.
- Confirma a mensagem de importação, o período e a data da previsão mostrados na app.
- Confere **Raciocínio → Auditoria, com a atividade escolhida no filtro global** para compreender os fatores e as fontes; compara praias e atividades.

O botão **não atualiza o código do site**. Altera apenas os dados das previsões e mantém o histórico guardado localmente.

## O que não é automático

- O ChatGPT não consulta dados ou publica no GitHub em segundo plano.
- O site não chama a OpenAI API nem contrata serviços externos.
- Não há sincronização entre telemóveis.
- Os dados de «ir à maré» e caça submarina não confirmam licenças nem acesso seguro.

## Novas versões da app

Alterações à interface ou à estrutura da app continuam a exigir envio dos ficheiros de código para GitHub Pages. A intenção é fazê-lo raramente. As previsões normais são atualizadas apenas com o JSON.

## Filtro global

Selecionar **Atividade** no topo do site para alterar simultaneamente todos os separadores. O botão **Importar atualização IA** recebe o ficheiro `forecast.json`, mas não instala versões novas de `app.js` ou `index.html`.

Para consultar diferenças de um local para cada atividade, escolher **Praias** e consultar a secção **Pesquisa local**: as fontes clicáveis distinguem características documentadas de hipóteses práticas.
