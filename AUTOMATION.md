# Atualização automática do Mar Sudoeste

O workflow `Atualizar previsão` corre às 00:17, 06:17, 12:17 e 18:17 UTC e também por `workflow_dispatch`. Portugal continental usa UTC no inverno e UTC+1 no verão; o cron do GitHub permanece em UTC.

O processo usa apenas Python standard library, Open-Meteo, IPMA e minutos incluídos do GitHub Actions. O Open-Meteo exige atribuição e fair use para utilização gratuita não comercial; não oferece uma quota ilimitada garantida. A API aberta do IPMA também deve ser consultada de forma moderada. O workflow limita a três pedidos simultâneos, faz no máximo quatro tentativas apenas para falhas temporárias e corre no máximo quatro vezes por dia. Os limites e minutos incluídos do GitHub Actions dependem do plano e da visibilidade do repositório; consultar [GitHub Actions billing](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions) e os [termos/preços do Open-Meteo](https://open-meteo.com/en/pricing) antes de aumentar a frequência. Repositórios públicos usam runners standard sem cobrança de minutos segundo a documentação do GitHub; repositórios privados dependem da franquia do plano e podem gerar custos depois dela.

## Ativação e teste

1. Rever e integrar o pull request.
2. Em **Actions → Atualizar previsão**, escolher **Run workflow** para o primeiro disparo manual.
3. Confirmar que o repositório permite GitHub Actions e que `GITHUB_TOKEN` tem acesso de escrita ao conteúdo. O workflow declara apenas `contents: write`.
4. Rever o commit do bot, `data/status.json` e a interface do site.

Ensaio local sem publicar nem alterar os ficheiros servidos:

```bash
python automation/update_forecast.py --dry-run
```

Validação sem rede:

```bash
python -m unittest discover -s tests -v
python automation/validate_forecast.py data/forecast.json
node --check app.js
node --check collector.js
node --check sw.js
```

## Política de falhas

A recolha precisa de meteorologia e pelo menos um modelo marítimo válido para as 14 zonas. Respostas incompletas ficam registadas. O cálculo só substitui `forecast.json` depois de passar a validação integral. Se a recolha, o cálculo ou a validação falhar, o forecast anterior permanece e `status.json` fica desatualizado com o erro. A escrita usa ficheiros temporários e substituição atómica. A concorrência do workflow impede duas publicações simultâneas; como não existe trigger `push`, o commit automatizado não cria ciclos.

O motor usa medianas por período entre centros disponíveis e regras fixas baseadas nos critérios existentes. Não chama ChatGPT/OpenAI. Não estima observações ausentes. Caça submarina não recebe nota final sem visibilidade real; ir à maré não recebe nota sem tabela oficial, luz e condições prudentes. A comparação com o forecast anterior é apenas diagnóstica: horizontes e fontes diferem, portanto não demonstra equivalência à análise humana.

## Diferenças face às avaliações ChatGPT

Os pesos publicados para surfcasting permanecem `23/14/16/14/18/15%` para onda, período, vento, luz, estrutura e maré. O motor determinístico substitui interpretação editorial por regras fixas e medianas de modelos. Não interpreta bancos, peixe, acessos, visibilidade ou legislação. A chuva do Mira é histórico de modelo por estação, agregado pela mediana das estações disponíveis; não é observação nem caudal. A luz usa nascer/pôr do sol da recolha. As marés só são usadas quando existe tabela IH incluída para a data. Estas diferenças podem produzir notas distintas do forecast anterior e estão registadas em `automation.comparison_with_previous`; não constituem equivalência validada.

## Ordem com o PR #2

O PR #2 altera apenas `collector.js` e acrescenta `collector.test.js`; este PR não modifica esses ficheiros. A ordem recomendada é integrar primeiro o PR #2 e depois atualizar/revalidar este PR contra `main`. Não há conflito de ficheiros conhecido e a automação Python mantém os mesmos quatro retries, backoff e limite de três pedidos sem depender do recolhedor do navegador.
