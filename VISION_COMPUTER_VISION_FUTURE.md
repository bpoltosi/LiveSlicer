# Visão computacional — evolução futura

## Status
Backlog futuro. Visão computacional **não faz parte** do pré-MVP de webcam + tecla Espaço e não bloqueia sua implementação básica.

## Motivação
Avaliar, depois de validar captura e exportação, se análise automática de imagem/vídeo agrega valor ao fluxo Live Slicer.

## Diretrizes para a futura implementação
- Definir casos de uso e resultados observáveis antes de selecionar modelos ou bibliotecas.
- Medir impacto em CPU/GPU, RAM, latência e continuidade da captura.
- Manter captura e gravação funcionando mesmo quando a análise falhar ou estiver indisponível.
- Tornar o processamento opcional e configurável; evitar dependência obrigatória de rede ou serviços externos sem decisão explícita.
- Criar testes e critérios de aceitação específicos para precisão, desempenho e comportamento em falhas.

## Pré-requisitos para retomar
1. Validar o fluxo manual com webcam, tecla Espaço e MP4 reproduzível.
2. Identificar um caso de uso prioritário (por exemplo, detecção de evento), com limites e falsos positivos aceitáveis.
3. Definir benchmarks em hardware-alvo.
4. Prototipar isoladamente e comparar o custo com a versão sem análise visual.

## Não incluído na versão pré-MVP
Nenhum modelo de visão computacional, detector de objetos, rastreamento, inferência em GPU ou serviço externo de IA é requisito desta entrega.
