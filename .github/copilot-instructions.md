# Copilot Instructions

Estas instruções orientam agentes de IA a trabalhar produtivamente neste repositório (`yt-playlist-summary`). Foque em manter a separação de responsabilidades entre coleta/transformação de mídia e transcrição/legendas.

## Visão Geral
Ferramenta em Python para: (1) baixar vídeos/áudios de playlists YouTube, (2) extrair e converter áudio (MP3 64kbps mono), (3) transcrever via Whisper API da OpenAI, (4) gerar legendas SRT e opcionalmente traduzir usando modelos GPT.

## Arquitetura
- `yt_playlist_summary.py`: Orquestra pipeline em etapas (download → extração → conversão → transcrição/SRT). Não contém lógica de transcrição interna; delega para `mywhisper.transcribe_audio_to_srt`.
- `mywhisper.py`: Módulo especializado em transcrição, chunking de arquivos grandes, cache, geração de SRT, tradução de legendas e fluxo "only-translation".
- Separação clara: manter `yt_playlist_summary.py` focado em I/O YouTube e pré-processamento de áudio; qualquer nova funcionalidade de legendas ou manipulação textual deve residir em `mywhisper.py` ou módulo dedicado.

## Fluxos Principais
1. Execução completa playlist:
   ```bash
   python yt_playlist_summary.py --url "PLAYLIST_URL" --api-key "$OPENAI_API_KEY"
   ```
2. Transcrição direta de áudio isolado:
   ```bash
   python mywhisper.py --input audio.mp3
   ```
3. Tradução de legenda existente (sem áudio):
   ```bash
   python mywhisper.py --only-translation subtitles.srt --translate pt
   ```

## Dependências & Ambiente
- Python >= 3.10 (compatível com 3.14; foi removido `audioop` no 3.14 e eliminamos `pydub`).
- FFmpeg + ffprobe exigidos (usados por yt-dlp e chamadas ffmpeg diretas; erros de duração indicam falta de ffprobe).
- Pacotes (veja `requirements.txt`): `yt-dlp`, `openai`, `python-dotenv`.
- Chave OpenAI: variável `OPENAI_API_KEY` ou parâmetro CLI (`--api-key`). Falta de chave ao não usar `--skip-transcription` resulta em retorno código 1 em `yt_playlist_summary.py`.

## Estrutura de Saída (criada dinamicamente)
```
output/
  downloads/   # Arquivos originais
  audio/       # Áudio extraído (se não audio-only)
  converted/   # Áudio convertido (64kbps mono)
  subtitles/   # Arquivos .srt gerados
```

## Chunking & Cache (mywhisper)
- Limite de tamanho: arquivos > 25MB são divididos em chunks de duração `--chunk-duration` (default 10 min) usando ffmpeg copy.
- Chunks temporários: `temp_chunks/` (removido sempre ao final).
- Cache: `.cache/<filehash>_chunk_XXXX.json` guarda transcrição bruta por chunk (usa MD5 do arquivo original). Alterações na lógica de geração de hash ou formato exigem limpeza manual (`--clear-cache`).

## Transcrição & Tradução
- Transcrição: Whisper (`client.audio.transcriptions.create`) com `response_format='verbose_json'` e granularidade por segmento.
- Tradução de áudio direto: usa `client.audio.translations.create` se `translate_to` for passado.
- Tradução de SRT existente: processamento em lotes (até 200 legendas) via `gpt-4.1-mini`; prompt gera JSON ou CSV conforme `--translation-format`.
- Qualidade: `quality_check_translations` procura placeholders, vazios e problemas de codificação; não corrige automaticamente.

## Logging & Verbosidade
- `yt_playlist_summary.py` usa `logging.basicConfig` e alterna nível para DEBUG com `--verbose`.
- `mywhisper.py` cria logger isolado (`whisper_transcriber`) com formatação simples (mensagem crua). Evite misturar estilos.
- Etapas demarcadas por blocos de `=` para legibilidade ao processar playlists.

## Convenções & Padrões
- Funções retornam caminhos de arquivos ou estruturas simples (dict/list); evite classes pesadas.
- Tratamento de erros: capturar exceptions por etapa e registrar `status='error'` sem abortar todo o lote.
- Conversão de áudio: ffmpeg puro; só ocorre se `--keep-original` não estiver definido; manter API dessa flag.
- SRT: timestamps gerados por `format_timestamp` (HH:MM:SS,mmm). Preserve exatamente esse formato se modificar.
- Tradução mantém `index` e `timestamp`; somente `text` é substituído.

## Extensões Seguras
Ao adicionar funcionalidades:
- Nova etapa no pipeline? Inserir após uma demarcação clara e manter `results` acumulando status por vídeo.
- Nova forma de pós-processamento de legendas? Implementar em função separada dentro de `mywhisper.py` e chamar após geração de SRT antes de salvar.
- Novos formatos de entrada: atualizar `SUPPORTED_FORMATS` e validar via `validate_audio_file`.

## Armadilhas Comuns
- FFmpeg ausente ou sem codecs mp3 → erros em extração/conversão.
- Python 3.14 em commits antigos → erro `ModuleNotFoundError: audioop`; solução: atualizar para versão sem pydub ou usar ffmpeg diretamente.
- Mudança em chunking sem limpeza de `.cache` → mistura de segmentos antigos e novos.
- Falta de `--api-key` quando não usando `--skip-transcription` → falha imediata.
- Tradução: respostas do modelo podem vir embrulhadas em blocos markdown; código já remove, manter essa lógica.

## Exemplos Rápidos
```bash
# Playlist, áudio apenas, sem transcrição
python yt_playlist_summary.py -u URL --audio-only --skip-transcription

# Transcrever e traduzir áudio direto para inglês
python mywhisper.py --input aula_pt.mp3 --translate en

# Limpar cache e forçar reprocessamento
python mywhisper.py --input longo.mp3 --clear-cache
```

## Prioridades do Agente
1. Preservar separação de módulos.
2. Manter compatibilidade de caminhos e estrutura de saída.
3. Evitar refatorações radicais sem necessidade (ex: não introduzir classes globais).
4. Minimizar dependências extras; alinhar com simplicidade atual.

---
Feedback desejado: Há alguma prática não documentada (ex: preferências de qualidade de áudio, limites de tempo, métricas) que deva ser incluída? Alguma seção ambígua?
