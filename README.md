# Live Slicer

Ferramenta para captura de vídeo e criação rápida de clipes pré-evento. O projeto reúne um gravador C++ para streams RTSP e um protótipo Python independente para webcam local.

> **Status:** em desenvolvimento. O pré-MVP Python está implementado com testes automatizados, mas ainda depende de validação manual com webcam física e análise dos vídeos exportados no computador-alvo.

## Visão do projeto

O Live Slicer busca permitir que o usuário registre momentos que aconteceram **antes** de acionar a gravação: o sistema mantém uma janela de vídeo recente em memória e, ao receber o comando, exporta o trecho anterior ao evento.

## Componentes

### C++ / RTSP — aplicação principal

Aplicação baseada em C++, Qt Core, FFmpeg e OpenCV, voltada a streams RTSP e captura multi-stream.

- Captura e reconexão de streams RTSP.
- Pré-buffer de vídeo para recuperar conteúdo anterior ao acionamento.
- Gravação em MP4/H.264, com possibilidade de evitar reencodificação quando o fluxo é compatível.
- Controle HTTP para iniciar e interromper gravações.
- Visualização de streams.
- Estrutura modular e documentação técnica.

O projeto inclui documentação específica para o desenho e a validação do pré-buffer RTSP. Consulte [docs/PREBUFFER_45S.md](docs/PREBUFFER_45S.md) para distinguir essa proposta da implementação de webcam Python.

### Python — webcam pre-MVP

Protótipo autônomo para validar a experiência de captura pré-evento com uma webcam local e a tecla **Espaço**.

- Buffer circular em memória com janela-alvo de até **45 segundos**, limitado pelo uso de RAM.
- Captura de webcam via OpenCV.
- Exportação do vídeo anterior ao acionamento para MP4/H.264 usando FFmpeg e `libx264`.
- Duração mínima padrão de **10 segundos** para evitar clipes muito curtos durante a inicialização.
- Exportação em segundo plano, mantendo o loop de captura e pré-visualização ativos.
- Apenas uma exportação por vez, evitando acumular snapshots de buffer.
- Indicadores de duração disponível, memória estimada e status de exportação.
- Limite de memória do buffer configurável (padrão de 512 MiB).

O protótipo é independente do serviço C++/RTSP e **não representa ainda uma integração multi-câmera**.

## Fluxo de captura (Python pre-MVP)

1. A webcam captura frames continuamente.
2. Os frames são comprimidos em JPEG e mantidos em um buffer circular.
3. O buffer conserva os frames mais recentes, até a janela configurada e o limite de RAM.
4. Ao pressionar **Espaço**, o sistema seleciona o vídeo anterior ao acionamento.
5. FFmpeg codifica e grava o clipe MP4 em segundo plano.
6. A pré-visualização continua ativa enquanto o arquivo é exportado.

## Tecnologias

| Área | Tecnologias |
|---|---|
| Aplicação RTSP | C++, Qt Core, FFmpeg, OpenCV |
| Protótipo webcam | Python, OpenCV |
| Exportação de vídeo | FFmpeg, libx264, H.264, MP4 |
| Build / validação | CMake, scripts de CI, testes automatizados |
| Documentação | Markdown, guias técnicos e checklists |

## Estrutura do repositório

- `include/`, `src/` — aplicação C++.
- `pre_mvp/` — protótipo Python independente de webcam.
- `tests/` — testes automatizados.
- `ci/` — scripts e configurações de validação.
- `docs/` — guias técnicos, arquitetura e checklists.
- `ext/ffmpeg_win/` — bibliotecas e headers FFmpeg para Windows.

## Instalação e execução do pre-MVP

### Requisitos

- Python 3.9 ou superior.
- OpenCV Python.
- FFmpeg com encoder `libx264`.

Instale as dependências Python a partir da raiz do repositório:

```bash
python -m pip install -r pre_mvp/requirements.txt
```

Verifique a instalação do FFmpeg e o encoder H.264:

```bash
ffmpeg -version
ffmpeg -hide_banner -encoders
```

A lista de encoders deve incluir `libx264`.

Inicie a aplicação:

```bash
python pre_mvp/live_slicer_pre_mvp.py
```

Para selecionar outra câmera:

```bash
python pre_mvp/live_slicer_pre_mvp.py --camera 1
```

Veja todas as configurações e parâmetros em [pre_mvp/README.md](pre_mvp/README.md).

## Testes

Execute os testes Python a partir da raiz:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Os testes cobrem validações de FFmpeg, limites de duração do clipe, seleção do buffer e comportamento de exportação em segundo plano. Eles **não substituem** a validação com webcam real, carga prolongada e inspeção dos arquivos MP4.

## Status e próximos passos

| Área | Status |
|---|---|
| Aplicação C++ para streams RTSP | Em desenvolvimento |
| Captura e reconexão RTSP | Implementada na base existente; validação depende do ambiente |
| Controle HTTP e visualização | Incluídos na aplicação C++ |
| Protótipo Python de webcam | Implementado (pre-MVP) |
| Buffer pré-evento de até 45 s (Python) | Implementado, sujeito ao limite de memória |
| Exportação MP4/H.264 em segundo plano | Implementada no protótipo |
| Testes automatizados Python | Disponíveis |
| Validação com webcam física e carga prolongada | Pendente |
| Integração entre protótipo Python e aplicação C++ | Não implementada |
| Visão computacional avançada | Roadmap futuro |

### Validação manual antes de considerar o pre-MVP pronto

- Confirmar acesso e permissões à webcam.
- Verificar rejeição de acionamentos antes da duração mínima.
- Exportar e reproduzir clipes de 10 e 45 segundos.
- Conferir codec, duração, resolução, FPS, qualidade e tamanho do arquivo.
- Confirmar que a pré-visualização permanece responsiva durante exportações.
- Testar acionamentos durante uma exportação, saída com Q/Esc, RAM e execução prolongada.

## Documentação

- [Índice de documentação](docs/README.md)
- [Guia do protótipo Python](pre_mvp/README.md)
- [Pré-buffer RTSP de 45 segundos](docs/PREBUFFER_45S.md)
- [Changelog](CHANGELOG.md)
- [Release notes da aplicação C++](ReleaseNotes.md)
- [Roadmap de visão computacional](VISION_COMPUTER_VISION_FUTURE.md)

## Roadmap futuro

- Validar o pre-MVP com webcam física e cenários de uso prolongado.
- Evoluir a captura RTSP e consolidar critérios de aceitação.
- Avaliar integração entre componentes após validação dos protótipos.
- Explorar visão computacional como recurso futuro, sem tratar como funcionalidade atual.

---

O Live Slicer é um projeto experimental/em evolução. Status de implementação, testes automatizados e validação em hardware são descritos separadamente para evitar considerar uma funcionalidade validada antes dos testes no ambiente real.
