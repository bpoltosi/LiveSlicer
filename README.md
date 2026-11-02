# Live Slicer

Projeto de captura de vídeo e geração de clips, composto por uma aplicação C++ para streams RTSP e um protótipo Python independente para captura de webcam.

## Componentes

### 1. Gravador C++ / RTSP

Aplicação baseada em C++, Qt Core, FFmpeg e OpenCV para trabalhar com múltiplas streams RTSP. A estrutura inclui:

- Captura e reconexão de streams.
- Pré-buffer de vídeo para preservar os segundos anteriores ao início de uma gravação.
- Gravação MP4 com fluxo H.264 sem reencodificação quando compatível.
- Controle HTTP para iniciar e parar gravações.
- Visualização de streams.

### 2. Python webcam pre-MVP

O diretório `pre_mvp/` contém um protótipo separado para capturar frames da webcam em buffer e exportar um clip anterior ao acionamento do usuário, utilizando FFmpeg.

Consulte [pre_mvp/README.md](pre_mvp/README.md) para requisitos, comandos, opções e verificações manuais. A execução real deve ser validada na máquina e webcam de destino.

## Estrutura relevante

- `include/` e `src/` — aplicação C++.
- `pre_mvp/` — protótipo Python de webcam.
- `tests/` — testes automatizados de componentes e scripts.
- `ci/` — arquivos e scripts de validação.
- `docs/` — documentação técnica, incluindo pré-buffer.
- `ext/ffmpeg_win/` — bibliotecas e headers FFmpeg para Windows.

## Dependências

A aplicação C++ utiliza CMake, Qt Core, FFmpeg e OpenCV, conforme a plataforma e configuração. O protótipo Python possui dependências próprias documentadas em `pre_mvp/requirements.txt` e requer FFmpeg para exportação.

## Testes

A suíte Python pode ser executada com:

```powershell
py -m unittest discover -s tests -v
```

Os scripts de CI e os testes C++/shell dependem das ferramentas e bibliotecas correspondentes. Consulte [docs/README.md](docs/README.md).

## Documentação

- [Índice de documentação](docs/README.md)
- [Pré-buffer de 45 segundos](docs/PREBUFFER_45S.md)
- [Guia do protótipo Python](pre_mvp/README.md)
- [Changelog](CHANGELOG.md)
- [Release notes](ReleaseNotes.md)
- [Visão futura de visão computacional](VISION_COMPUTER_VISION_FUTURE.md)

## Status

Projeto em evolução. Testes automatizados não substituem a validação com câmera física, estabilidade em sessões longas e integridade dos arquivos MP4 exportados. Visão computacional avançada permanece como evolução futura, não como requisito do protótipo atual.