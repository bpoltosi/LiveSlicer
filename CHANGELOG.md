# Changelog

## Pré-MVP webcam + Espaço (2026-10-22)

- Adiciona protótipo Python independente usando webcam local e tecla Espaço.
- Mantém buffer circular de vídeo pré-evento de até 45 segundos, sujeito ao limite de RAM.
- Exporta MP4/H.264 com FFmpeg/libx264 em segundo plano.
- Define duração mínima de clipe de 10 segundos por padrão.
- Faz os clipes subsequentes começarem no final do clipe anterior, sem sobreposição; rejeita intervalos curtos ou início perdido no buffer.
- Adiciona bootstrap resiliente para localizar/instalar FFmpeg e testes unitários.
- Documenta procedimento de validação manual.

### Limitações conhecidas
A aceitação real com webcam física, foco da janela, carga prolongada e inspeção dos arquivos MP4 ainda precisa ser executada no computador-alvo. Esta alteração documenta e fornece o pré-MVP; não declara a validação física concluída.

Visão computacional permanece como evolução futura, descrita em VISION_COMPUTER_VISION_FUTURE.md.
