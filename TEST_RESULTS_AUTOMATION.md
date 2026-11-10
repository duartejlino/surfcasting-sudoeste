# Resultados da automação

Validação executada em 10 de novembro de 2026:

- `python -m unittest discover -s tests -v`: 11 testes aprovados.
- `python -m py_compile collect_sources_14_spots.py automation/*.py tests/*.py`: aprovado.
- `node --check app.js`, `collector.js` e `sw.js`: aprovado.
- Forecast anterior: continua válido no verificador existente e não foi alterado durante os ensaios.
- Ensaio integral `python automation/update_forecast.py --dry-run`: iniciado sem publicar, mas a recolha real foi interrompida depois de o ambiente Codex devolver `403 CONNECT` para `api.open-meteo.com`. A allowlist desta sessão não contém Open-Meteo. O runner normal de GitHub Actions não herda esta política; o primeiro `workflow_dispatch` deve confirmar a integração real antes de confiar no agendamento.

Os testes cobrem retries 408/429/500/502/503/504 por configuração e exercitam HTTP 503, falha de rede, HTTP não repetível, intervalos 2/5/10, quatro tentativas, três workers, 14 zonas, cinco modalidades, seis períodos, quatro espécies, três níveis de surf, intervalos de notas, segurança, visibilidade ausente, cobertura crítica ausente, comparação diagnóstica com o forecast anterior, preservação do ficheiro publicado, permissões do workflow e cache network-first.

Limitação de validação: não existem observações reais suficientes de resultados humanos para provar equivalência com a análise manual anterior. O motor declara essa lacuna no JSON e a comparação de distribuições não é tratada como validação de verdade.
