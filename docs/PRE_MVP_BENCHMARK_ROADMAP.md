# Pré-MVP: roadmap de benchmarks, qualidade visual e otimização

## Objetivo

Medir de forma reproduzível a qualidade visual e o consumo de recursos do pré-MVP de webcam antes de alterar o pipeline. Os testes funcionais existentes já foram validados; este plano não prioriza reexecutá-los sem motivo. A qualidade visual percebida é o problema principal, e as decisões devem ser baseadas em medições de RAM, CPU, captura e exportação.

A visão computacional continua fora do escopo e permanece registrada como trabalho futuro independente.

## Regras de execução

1. Executar as etapas na ordem indicada, respeitando as dependências.
2. Estabelecer e guardar uma baseline antes de alterar defaults ou arquitetura.
3. Alterar uma variável por experimento e usar entradas idênticas para comparar resultados.
4. Separar benchmarks sintéticos (adequados ao CI e sem webcam física) de medições de hardware real.
5. Reportar separadamente memória estimada do buffer, RSS/pico do processo e tamanho do arquivo.
6. Não declarar que houve melhoria com base apenas em tamanho do MP4 ou CPU: considerar qualidade, fluidez, RAM, tempo de exportação e responsividade.
7. Não definir limites universais antes de medir no computador-alvo.

## Sequência de trabalho

### Etapa 1 — Harness reproduzível e formato de resultados

**Issue planejada:** [Pre-MVP][Benchmark 1/6] Criar harness reproduzível e formato de resultados

**Objetivo:** criar a infraestrutura comum usada pelas demais medições.

**Escopo**
- Criar um comando/script de benchmark independente do fluxo normal da aplicação.
- Definir um formato versionado de resultados (JSON ou CSV) com timestamp, versão/commit, sistema operacional, versões de Python/OpenCV/FFmpeg, parâmetros e métricas.
- Separar modo sintético, executável em CI, de modo opcional com hardware real.
- Permitir selecionar diretório de saída, duração e número de repetições por argumentos.
- Registrar falhas e ambiente incompleto explicitamente; ausência de webcam não deve impedir o modo sintético.
- Documentar como executar e comparar execuções.

**Critérios de aceite**
- Uma execução sintética produz um artefato legível por máquina e um resumo legível por humanos.
- O resultado identifica configuração e ambiente suficientes para comparar execuções.
- Não exige webcam física nem modifica os testes funcionais existentes.
- Há exemplo de resultado e instruções reproduzíveis.

**Dependências:** nenhuma; é a primeira etapa.

### Etapa 2 — Métricas de captura e buffer circular

**Issue planejada:** [Pre-MVP][Benchmark 2/6] Medir desempenho real da captura e do buffer circular

**Objetivo:** medir a taxa real de captura e o custo de armazenar frames JPEG.

**Escopo**
- Registrar resolução solicitada versus efetiva.
- Medir FPS efetivo, distribuição dos intervalos entre frames e jitter.
- Contabilizar falhas de leitura, frames inválidos e quedas de captura.
- Medir tempo de codificação JPEG por frame.
- Registrar bytes por frame, tamanho atual/pico do buffer, duração e comportamento do limite máximo de memória.
- Disponibilizar modo sintético determinístico e modo opcional de hardware com webcam real.

**Critérios de aceite**
- Métricas incluídas no formato comum da Etapa 1.
- Modo sintético repetível, sem dispositivo local.
- Modo hardware reporta claramente resolução/FPS efetivos e falhas; não mascara falha ao abrir a câmera.
- Comparação de configurações JPEG sem alterações manuais no código.
- Documentar a diferença entre memória estimada do buffer e memória total do processo.

**Dependências:** Etapa 1.

### Etapa 3 — RAM, CPU e custo de exportação

**Issue planejada:** [Pre-MVP][Benchmark 3/6] Instrumentar RAM, CPU e tempo de exportação

**Objetivo:** medir o custo real da captura/exportação, incluindo picos fora do contador do buffer.

**Escopo**
- Medir RSS do processo e pico observado, mantendo o tamanho estimado do buffer como métrica separada.
- Medir CPU média/pico quando suportado e duração de exportação.
- Registrar duração e tamanho do MP4, FPS de entrada/saída e código de saída do FFmpeg.
- Separar cenários: captura ociosa, exportação única e exportações repetidas.
- Observar crescimento persistente de memória entre ciclos sem classificar automaticamente caches como vazamento.
- Indicar explicitamente métricas indisponíveis em determinado sistema operacional.

**Critérios de aceite**
- Resultados no formato comum e com parâmetros do FFmpeg.
- Baseline executável sem webcam via frames sintéticos.
- Medições antes/durante/depois da exportação para revelar picos.
- Relatório diferencia RSS, memória do buffer e tamanho do arquivo.
- Execuções repetidas comparáveis e limitações por sistema operacional documentadas.

**Dependências:** Etapa 1.

### Etapa 4 — Testes automatizados de qualidade visual

**Issue planejada:** [Pre-MVP][Benchmark 4/6] Criar testes automatizados de qualidade visual do pipeline

**Objetivo:** localizar a perda de detalhes na compressão JPEG do buffer e/ou na exportação H.264/MP4.

**Escopo**
- Gerar cenas sintéticas determinísticas com gradientes, texto/linhas finas, bordas, detalhes de cor e movimento simulado.
- Comparar imagem original com JPEG codificado/decodificado e com frames extraídos do MP4.
- Calcular PSNR e SSIM quando disponíveis; registrar claramente quando uma métrica opcional não estiver instalada.
- Validar integridade via FFprobe: dimensões, FPS, duração, codec e quantidade aproximada de frames.
- Isolar a perda da etapa JPEG da perda H.264; CRF não recupera detalhes já perdidos no JPEG.
- Armazenar métricas e parâmetros para comparação.

**Critérios de aceite**
- Testes sintéticos executáveis sem webcam e aptos ao CI.
- Resultado identifica etapa medida e parâmetros JPEG/H.264.
- Regressão acima de limite configurável produz falha ou aviso explícito.
- Limite inicial documentado como calibrável, podendo começar informativo até estabelecer baseline.
- MP4 corrompido ou com metadados essenciais divergentes gera erro claro.

**Dependências:** Etapa 1.

### Etapa 5 — Matriz de experimentos para identificar a origem da perda visual

**Issue planejada:** [Pre-MVP][Qualidade 5/6] Executar matriz de experimentos e identificar a origem da perda visual

**Objetivo:** usar os dados para identificar os fatores que explicam a qualidade visual percebida como baixa.

**Pré-requisitos:** Etapas 1 a 4.

**Plano experimental — uma variável por vez**
1. Resolução e FPS efetivos da webcam versus valores solicitados.
2. JPEG quality 98 versus 100; medir custo em bytes/RAM e, se viável, comparar com buffer sem recompressão JPEG como controle.
3. H.264 CRF 18 versus 16 e 20, mantendo preset e outras opções fixos.
4. Comparar o preset atual com alternativas apenas se houver hipótese e medição relevante.
5. Avaliar a influência de YUV 4:2:0/subamostragem de crominância em detalhes coloridos.
6. Verificar discrepâncias de FPS, repetição/descarte de frames e fluidez.

Não executar todas as combinações simultaneamente. Para cada experimento, registrar hipótese, configuração, métricas, amostras e conclusão.

**Critérios de aceite**
- Tabela de parâmetros, métricas de qualidade, pico de RAM, CPU, duração de exportação e tamanho de arquivo.
- Identificação da etapa dominante ou declaração explícita de evidência inconclusiva.
- Amostras comparáveis e avaliação visual manual no computador-alvo quando necessário.
- Recomendação fundamentada em dados, sem otimizar apenas tamanho/CPU.
- Defaults atuais preservados até decisão fundamentada.

**Dependências:** Etapas 1 a 4.

### Etapa 6 — Aplicar melhorias com limites medidos

**Issue planejada:** [Pre-MVP][Otimização 6/6] Aplicar melhorias de qualidade com limites de recursos medidos

**Objetivo:** implementar apenas mudanças sustentadas por evidência, elevando a qualidade sem comprometer responsividade ou recursos.

**Pré-requisitos:** Etapa 5 concluída e baseline medida no computador-alvo.

**Escopo**
- Selecionar mudanças com ganho mensurável e custo aceitável em RAM, CPU, latência de exportação e tamanho do arquivo.
- Implementar mudanças pequenas e isoladas; manter parâmetros configuráveis quando apropriado.
- Reexecutar exatamente os mesmos benchmarks antes/depois.
- Atualizar documentação com defaults, trade-offs medidos e comandos de reprodução.
- Preservar os testes funcionais já validados e acrescentar regressões apenas onde a mudança afetar comportamento.
- Dividir em PRs pequenos quando existirem soluções independentes.

**Critérios de aceite**
- Relatório antes/depois inclui qualidade visual, RSS pico, CPU, tempo de exportação, tamanho do arquivo e FPS.
- Regressões de recursos/responsividade explicitadas e avaliadas contra a baseline do computador-alvo.
- Defaults finais justificados e documentados.
- Testes relevantes passam sem enfraquecer testes existentes.

**Dependências:** Etapas 1 a 5.

## Resultado esperado

Ao concluir a sequência, teremos uma baseline reproduzível, medições separadas de captura/recursos/qualidade, uma explicação baseada em evidências para a perda visual e somente então alterações de otimização avaliadas por comparação antes/depois.

## Observação sobre GitHub Issues

A tentativa de criar Issues para cada etapa retornou erro da API do GitHub indicando que o recurso Issues está desabilitado neste repositório (HTTP 410). Este documento preserva os seis títulos, descrições, critérios de aceite e dependências para que possam ser convertidos em Issues individuais assim que o recurso for habilitado. O PR que adiciona este plano pode ser revisado normalmente, mas não substitui as Issues separadas solicitadas.
