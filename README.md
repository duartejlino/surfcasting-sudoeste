# Surfcasting Sudoeste v3 — motor explicável

PWA estática para apresentar previsões de surfcasting entre a Costa de Santo André e Vila Nova de Milfontes.

## Arquitetura

A app é deliberadamente separada do motor de análise:

1. **ChatGPT / motor de análise** recolhe e interpreta dados, histórico e regras locais.
2. Gera `data/forecast.json` no esquema v3.
3. **A app** apresenta ranking, confiança e raciocínio fator a fator.
4. O utilizador regista as pescarias na app e exporta `surfcasting_historico_para_chatgpt.json`.
5. O histórico é usado numa análise posterior para recalibrar o modelo e gerar nova previsão.

Enquanto não existir publicação automática, o botão **Importar atualização IA** permite carregar um `forecast.json` novo sem alterar código.

## Explicabilidade

Cada avaliação praia × período × espécie guarda:

- nota final (0–10);
- confiança da análise;
- resumo;
- "porque não é 10/10";
- fatores individuais;
- valor observado;
- nota de cada fator;
- peso;
- impacto na nota final;
- fonte;
- confiança do fator;
- justificação textual;
- análise de sensibilidade (o que faria a nota subir/descer).

## Histórico

O histórico fica em `localStorage` e pode ser exportado/importado. Cada saída inclui um snapshot integral da previsão usada nesse momento para permitir comparar previsão vs realidade.

## Execução local

Não abrir apenas por `file://`. Usa um servidor local, por exemplo:

```bash
python -m http.server 8080
```

Depois abre `http://localhost:8080`.

## Publicação

Compatível com GitHub Pages, Cloudflare Pages, Netlify ou Vercel, sem processo de build.
