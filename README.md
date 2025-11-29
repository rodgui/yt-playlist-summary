# yt-playlist-summary

Ferramenta em Python para:
- Baixar vídeos/áudios de playlists YouTube
- Extrair e converter áudio (MP3 64kbps mono)
- Transcrever via OpenAI Whisper
- Gerar legendas SRT
- Traduzir SRT existente via GPT-4.1-mini
- **Gerar material de estudo consolidado** a partir das legendas da playlist

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
- `--no-checkpoint` desabilita checkpoint/retomada (força reprocessamento completo)
- `--clear-checkpoint` limpa checkpoint existente e reinicia do zero

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

## Sistema de Checkpoint/Retomada

**Novidade:** O sistema agora possui checkpoint automático para retomar downloads interrompidos!

### Como Funciona

1. **Criação automática**: Ao iniciar o processamento, um arquivo `.checkpoint_<id>.json` é criado em `output/`
2. **Registro contínuo**: Cada vídeo baixado com sucesso é marcado como "OK" no checkpoint
3. **Retomada inteligente**: Se o processo for interrompido (Ctrl+C, erro, etc), ao reiniciar o mesmo comando, apenas vídeos não concluídos serão processados

### Exemplo de Uso

```bash
# Primeira execução - processa 10 vídeos, mas é interrompida no vídeo 5
python yt_playlist_summary.py --url "PLAYLIST_URL" --api-key "$OPENAI_API_KEY"
# ^C (interrompido pelo usuário)

# Segunda execução - retoma do vídeo 6 automaticamente
python yt_playlist_summary.py --url "PLAYLIST_URL" --api-key "$OPENAI_API_KEY"
# ✅ Já concluídos: 5/10
# ⏭️  Pulando vídeos já processados...
```

### Opções de Controle

```bash
# Desabilitar checkpoint (processar tudo novamente)
python yt_playlist_summary.py --url "PLAYLIST_URL" --no-checkpoint

# Limpar checkpoint e reiniciar do zero
python yt_playlist_summary.py --url "PLAYLIST_URL" --clear-checkpoint

# Ver progresso atual sem processar
# O checkpoint é carregado automaticamente e mostra status
```

### Estrutura do Checkpoint

O arquivo `.checkpoint_<id>.json` contém:
```json
{
  "playlist_id": "abc123...",
  "playlist_url": "https://...",
  "total_videos": 10,
  "videos": {
    "video_id_1": {
      "index": 1,
      "title": "Video Title",
      "status": "completed",
      "subtitle_source": "youtube",
      "downloaded_at": "2025-11-28T..."
    },
    "video_id_2": {
      "index": 2,
      "title": "Another Video",
      "status": "pending"
    }
  }
}
```

### Notas Importantes

- Checkpoint é específico por playlist URL (diferentes URLs = diferentes checkpoints)
- Vídeos com `status='failed'` são reprocessados na próxima execução
- Arquivos já baixados no disco NÃO são re-baixados mesmo sem checkpoint
- Seguro interromper a qualquer momento (Ctrl+C)

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

## Geração de Material de Estudo

Após processar uma playlist e obter as legendas (via YouTube ou Whisper), você pode gerar um material de estudo consolidado usando GPT-4.1-mini:

### 5) Gerar material de estudo a partir de legendas existentes

```bash
python generate_study_material.py \
  --subtitle-dir ./output/subtitles \
  --api-key "$OPENAI_API_KEY" \
  --output material_estudo.md
```

**O que faz:**
- Lê todos os arquivos `.srt` do diretório
- Consolida as transcrições em ordem cronológica
- Envia para GPT-4.1-mini com prompt educacional estruturado
- Gera material com:
  - Resumo executivo da playlist
  - Conceitos-chave explicados
  - Análise por vídeo (resumo, pontos principais, exemplos)
  - Exemplos práticos consolidados
  - Pontos de ação (checklist)
  - Glossário de termos técnicos
  - Referências com timestamps

**Opções úteis:**
- `-l/--language pt|en` - idioma do material (default: pt)
- `--skip-gpt` - apenas consolida texto, sem enviar para GPT
- `-i/--interactive` - pede confirmação para playlists grandes (>50k tokens)
- `-v/--verbose` - logging detalhado

**Integração com pipeline principal:**
```bash
# Processar playlist E gerar material de estudo automaticamente
python yt_playlist_summary.py \
  --url "PLAYLIST_URL" \
  --api-key "$OPENAI_API_KEY" \
  --generate-study-material \
  --study-language pt
```

**Estimativa de custos:**
- O script calcula tokens antes de enviar
- GPT-4.1-mini: ~$0.15 por milhão de tokens (entrada) + ~$0.60 (saída)
- Playlist típica (5-10 vídeos): ~$0.02-0.05 USD
- Playlists grandes (>20 vídeos): modo interativo recomendado

**Arquivos gerados:**
- `study_material_TIMESTAMP.md` - material final processado por IA
- `study_material_TIMESTAMP_consolidated.md` - transcrições brutas (backup)

## Desenvolvimento

- `yt_playlist_summary.py`: orquestra pipeline (download → extração → conversão → transcrição/SRT).
- `mywhisper.py`: transcrição e rotinas de legenda/translation.
- `translate_sub.py`: tradução de SRT com GPT-4.1-mini.
- `generate_study_material.py`: geração de material educacional consolidado via GPT.
- `checkpoint_manager.py`: gerenciamento de checkpoint para retomada de downloads.

**Testes:**
- `test_checkpoint.py`: testes unitários do sistema de checkpoint.

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

Gerar material de estudo após processar:
```bash
# Opção 1: Integrado ao pipeline principal
python yt_playlist_summary.py \
  --url "https://www.youtube.com/playlist?list=EXEMPLO" \
  --prefer-existing-subtitles \
  --subtitle-languages "pt-BR,en" \
  --api-key "$OPENAI_API_KEY" \
  --generate-study-material

# Opção 2: Processar legendas já existentes
python generate_study_material.py \
  --subtitle-dir ./output/subtitles \
  --api-key "$OPENAI_API_KEY" \
  -i
```

**Exemplo com Checkpoint (interrupção e retomada):**
```bash
# Primeira execução - processando playlist grande
python yt_playlist_summary.py --url "PLAYLIST_URL" --api-key "$OPENAI_API_KEY"
# Processando vídeo 3/10...
# ^C (usuário interrompe)

# Segunda execução - retoma automaticamente
python yt_playlist_summary.py --url "PLAYLIST_URL" --api-key "$OPENAI_API_KEY"
# 🔄 RETOMANDO DOWNLOAD
# ✅ Já concluídos: 3/10
# ⏭️  Pulando vídeos já processados...
# Processando vídeo 4/10...
```

Dicas:
- Sem `-v` os warnings do yt-dlp são suprimidos; com `-v` você vê detalhes da extração.
- Se não quiser usar Whisper, passe `--skip-transcription` (vídeos sem legendas ficarão sem SRT).
- Ajuste `--download-delay` para reduzir risco de rate-limiting em playlists grandes.
- Use `--generate-study-material` para criar automaticamente material educacional consolidado ao final.
- Sistema de checkpoint permite interromper e retomar processamento a qualquer momento (Ctrl+C é seguro!).
