# yt-playlist-summary

Ferramenta em Python para:
- Baixar vídeos/áudios de playlists YouTube
- Extrair e converter áudio (MP3 64kbps mono)
- Transcrever via OpenAI Whisper
- Gerar legendas SRT
- Traduzir SRT existente via GPT-4.1-mini

## Requisitos

- Python 3.10+
- FFmpeg e ffprobe instalados no sistema
- Pacotes: `yt-dlp`, `openai`, `python-dotenv` (veja `requirements.txt`)
- OPENAI_API_KEY definido ou passado via `--api-key`

## Estrutura de Saída

```
output/
  downloads/   # arquivos originais baixados
  audio/       # áudio extraído (quando necessário)
  converted/   # áudio convertido (64kbps mono)
  subtitles/   # arquivos .srt gerados/copiados
```

## Uso

### 1) Processar uma playlist completa
Baixa a playlist, usa legendas nativas se disponíveis, caso contrário transcreve com Whisper.

```bash
python yt_playlist_summary.py --url "PLAYLIST_URL" --api-key "$OPENAI_API_KEY"
```

Opções úteis:
- `--prefer-existing-subtitles` tenta usar legendas nativas (manuais/automáticas)
- `--subtitle-languages "pt-BR,en"` define idiomas preferidos para busca
- `--interactive` mostra prévia da playlist, confirma download e permite escolher idiomas por vídeo
- `--download-delay 5` define atraso entre downloads para evitar rate limiting
- `--skip-transcription` pula etapa de Whisper (apenas download/cópia de SRT)

Exemplos:
```bash
# Usar legendas nativas se existirem; caso contrário, Whisper
python yt_playlist_summary.py --url "PLAYLIST_URL" --prefer-existing-subtitles --subtitle-languages "pt-BR,en" --api-key "$OPENAI_API_KEY"

# Modo interativo com escolha de idioma por vídeo
python yt_playlist_summary.py --url "PLAYLIST_URL" --prefer-existing-subtitles --subtitle-languages "pt-BR,en" -i --api-key "$OPENAI_API_KEY"
```

### 2) Comportamento inteligente: pular extração/conversão quando há legendas nativas
- Se `--prefer-existing-subtitles` estiver ativo e o vídeo tiver legendas nos idiomas desejados, o pipeline copia as .srt para `output/subtitles` e pula extração/conversão de áudio.
- Se não houver legendas, extrai e converte áudio, depois transcreve com Whisper.

Sufixos:
- Transcrições Whisper são salvas como `nome_do_video.whisper.srt`
- Legendas nativas preservam sufixo de idioma: ex. `nome.pt-BR.srt`, `nome.en.srt`

### 3) Traduzir um arquivo .srt existente
Use o script dedicado `translate_sub.py` com GPT-4.1-mini:

```bash
python translate_sub.py --input ./output/subtitles/video.pt-BR.srt --source pt-BR --target en --api-key "$OPENAI_API_KEY"
```

Saída:
- Cria `video.translated.en.srt` ao lado do arquivo de entrada.
- Mantém índices e timestamps, traduz apenas o texto.

Outros exemplos:
```bash
# Traduzir de EN para PT-BR
python translate_sub.py -i ./output/subtitles/video.en.srt -s en -t pt-BR

# Dry-run (não grava arquivo, mostra amostra)
python translate_sub.py -i legenda.srt -s pt -t en --dry-run
```

### 4) Transcrever áudio isolado (opcional)
```
python mywhisper.py --input ./output/converted/audio.mp3 --api-key "$OPENAI_API_KEY"
```

## Logging e Verbosidade

- Sem `-v`: logs essenciais, warnings do yt-dlp suprimidos.
- Com `-v`: logs detalhados (inclui avisos do yt-dlp).

Mensagens de etapa:
- Consultando playlist
- Baixando vídeo
- Verificando/baixando legendas
- Preparando Whisper (quando necessário)
- Extraindo/convertendo áudio (apenas quando Whisper será usado)
- Enviando para OpenAI para geração de legenda

## Notas e Armadilhas

- FFmpeg/ffprobe são obrigatórios; erros de duração ou conversão geralmente indicam falta de ffprobe.
- Se `--skip-transcription` e não houver legendas, nenhum SRT será gerado.
- No Python 3.14, `audioop` foi removido; usamos ffmpeg puro (sem `pydub`).
- Para playlists muito grandes, use `--download-delay` para evitar bloqueios.

## Desenvolvimento

- `yt_playlist_summary.py`: orquestra pipeline (download → extração → conversão → transcrição/SRT).
- `mywhisper.py`: transcrição e rotinas de legenda/translation.
- `translate_sub.py`: tradução de SRT com GPT-4.1-mini.

Mantenha a separação de responsabilidades; novas funcionalidades de texto/legenda devem residir em módulos dedicados (ex.: `mywhisper.py` ou scripts como `translate_sub.py`).

## Exemplo completo

Cenário: playlist com 3 vídeos
- Vídeo 1: possui legendas nativas pt-BR e en (pula extração/conversão; copia SRTs)
- Vídeo 2: sem legendas nos idiomas solicitados (usa Whisper; gera .whisper.srt)
- Vídeo 3: possui apenas legendas automáticas en (copia SRT automática)

Comando:
```bash
python yt_playlist_summary.py \
  --url "https://www.youtube.com/playlist?list=EXEMPLO" \
  --prefer-existing-subtitles \
  --subtitle-languages "pt-BR,en" \
  --download-delay 5 \
  -i \
  --api-key "$OPENAI_API_KEY"
```

Fluxo esperado (resumo dos logs essenciais):
- Consultando playlist
- Exibe prévia dos vídeos e tempo total
- Verifica disponibilidade de legendas por vídeo
- Para vídeos sem idiomas solicitados, pergunta se deseja ver idiomas disponíveis ou usar Whisper
- Baixa vídeos e legendas conforme escolhas
- Para vídeos com Whisper:
  - Extrai e converte áudio (64kbps mono)
  - Envia para OpenAI Whisper e gera SRT com sufixo .whisper.srt

Estrutura de saída:
```
output/
  downloads/
    01_Titulo1.mp4
    02_Titulo2.mp4
    03_Titulo3.mp4
    01_Titulo1.pt-BR.srt
    01_Titulo1.en.srt
    03_Titulo3.en.auto.srt
  audio/
    02_Titulo2.mp3                      # apenas onde Whisper foi usado
  converted/
    02_Titulo2_64kbps_mono.mp3          # apenas onde Whisper foi usado
  subtitles/
    01_Titulo1.pt-BR.srt                # legenda nativa
    01_Titulo1.en.srt                   # legenda nativa
    02_Titulo2.whisper.srt              # transcrição Whisper
    03_Titulo3.en.auto.srt              # legenda automática
```

Traduzir uma legenda para outro idioma:
```bash
# Exemplo: traduzir pt-BR -> en
python translate_sub.py \
  --input ./output/subtitles/01_Titulo1.pt-BR.srt \
  --source pt-BR \
  --target en \
  --api-key "$OPENAI_API_KEY"
# Saída: ./output/subtitles/01_Titulo1.pt-BR.translated.en.srt
```

Dicas:
- Sem `-v` os warnings do yt-dlp são suprimidos; com `-v` você vê detalhes da extração.
- Se não quiser usar Whisper, passe `--skip-transcription` (vídeos sem legendas ficarão sem SRT).
- Ajuste `--download-delay` para reduzir risco de rate-limiting em playlists grandes.
