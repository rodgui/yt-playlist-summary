#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Playlist Summary Tool

A solution that receives a YouTube playlist URL, downloads videos,
extracts audio, converts to mp3, and uses mywhisper for transcription
and SRT subtitle generation.

Created by Rodgui (rod.gui@gmail.com / @rodgui on GitHub)
"""
       
import argparse
import io
import logging
import os
import sys
       
# Forçar UTF-8 no stdout/stderr para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
       
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
       
import yt_dlp
       
# Import checkpoint manager
from checkpoint_manager import CheckpointManager, get_checkpoint_path

# Import study material generator
from generate_study_material import generate_playlist_study_content

# Import language utilities
from language_utils import (
    get_default_output_language,
    get_default_source_languages,
    get_system_language,
    parse_language_list,
)

# Import transcription functionality from mywhisper
from mywhisper import transcribe_audio_to_srt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging level based on verbosity."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    else:
        # Suprimir warnings do yt-dlp quando não estiver em verbose
        logging.getLogger("yt_dlp").setLevel(logging.ERROR)
        logging.getLogger().setLevel(logging.INFO)


# Extensões de mídia aceitas para processamento (evita tratar .srt como mídia)
SUPPORTED_MEDIA_EXTS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mp3",
    ".m4a",
    ".aac",
    ".wav",
    ".flac",
    ".ogg",
}


def _sanitize_base_title(title: str) -> str:
    r"""
    Normaliza o título para nome de arquivo seguro em todos os sistemas operacionais.
    Remove/substitui caracteres problemáticos para Windows, macOS e Linux.
    """
    if not title:
        return "untitled"

    t = title

    # Normaliza caracteres Unicode similares para ASCII
    t = t.replace("：", ":")  # fullwidth colon → regular colon
    t = t.replace("／", "/")  # fullwidth slash
    t = t.replace("＼", "\\")  # fullwidth backslash

    # Substitui separadores de caminho por hífen
    t = t.replace("/", " - ").replace("\\", " - ")

    # Remove caracteres proibidos no Windows: < > : " | ? *
    # Mantém hífen, underscore, espaço, letras, números e acentos
    forbidden_chars = '<>:"|?*'
    for char in forbidden_chars:
        t = t.replace(char, "")

    # Remove caracteres de controle (0x00-0x1F)
    t = "".join(c for c in t if ord(c) >= 32)

    # Comprime espaços múltiplos
    while "  " in t:
        t = t.replace("  ", " ")

    # Remove espaços no início/fim
    t = t.strip()

    # Remove pontos no final (Windows não permite)
    t = t.rstrip(".")

    # Nomes reservados do Windows
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    if t.upper() in reserved_names:
        t = f"_{t}"

    # Limita tamanho (255 é o máximo em muitos sistemas, mas deixamos margem para extensão)
    if len(t) > 200:
        t = t[:200]

    # Se ficou vazio após sanitização
    if not t:
        return "untitled"

    return t


def _ensure_unique_path(path: str) -> str:
    """
    Garante que o caminho seja único, adicionando sufixo numérico se necessário.
    Usa pathlib.Path para compatibilidade cross-platform.
    """
    p = Path(path)
    if not p.exists():
        return str(p)

    counter = 1
    while True:
        new_path = p.parent / f"{p.stem}_{counter}{p.suffix}"
        if not new_path.exists():
            return str(new_path)
        counter += 1


def _rename_downloads_to_desired_names(
    downloads_dir: str, id_to_desired: Dict[str, str]
) -> None:
    """
    Renomeia arquivos baixados de video_id para o título desejado.
    Usa pathlib.Path para compatibilidade cross-platform.
    Reconhece padrões: VIDEO_ID.ext, VIDEO_ID.LANG.ext, VIDEO_ID.NA.LANG.ext
    """
    dir_path = Path(downloads_dir)
    if not dir_path.exists():
        return

    # Extensões aceitas (mídia + legendas)
    valid_exts = SUPPORTED_MEDIA_EXTS | {".srt", ".vtt", ".ass", ".sub"}

    for file_path in dir_path.iterdir():
        if not file_path.is_file():
            continue

        # Ignora arquivos que não são mídia nem legendas
        if file_path.suffix.lower() not in valid_exts:
            continue

        # Extrai o video_id do nome do arquivo
        # Padrões possíveis:
        #   VIDEO_ID.mp4
        #   VIDEO_ID.en.srt
        #   VIDEO_ID.NA.en.srt (YouTube auto-generated marker)
        #   VIDEO_ID.NA.pt-BR.srt
        stem = file_path.stem
        parts = stem.split(".")
        video_id = parts[0]

        if video_id not in id_to_desired:
            continue

        desired_title = id_to_desired[video_id]
        sanitized_title = _sanitize_base_title(desired_title)

        # Reconstrói o nome preservando sufixos de idioma
        # Remove 'NA' (marcador do YouTube para auto-generated) se presente
        suffix_parts = [p for p in parts[1:] if p.upper() != "NA"]

        if suffix_parts:
            new_stem = f"{sanitized_title}.{'.'.join(suffix_parts)}"
        else:
            new_stem = sanitized_title

        new_path = file_path.parent / f"{new_stem}{file_path.suffix}"
        new_path = Path(_ensure_unique_path(str(new_path)))

        if file_path != new_path:
            try:
                file_path.rename(new_path)
                logger.debug(f"Renomeado: {file_path.name} → {new_path.name}")
            except OSError as e:
                logger.warning(f"Não foi possível renomear {file_path.name}: {e}")


def _normalize_lang_variants(lang: str) -> list[str]:
    """
    Normaliza códigos de idioma para múltiplas variantes aceitáveis:
    'pt-BR' -> ['pt-br','ptbr','pt_br','ptbr','pt']
    'enUS'  -> ['enus','en_us','en-us','en']
    """
    l = lang.strip().lower()
    base = l.split("-")[0].split("_")[0]
    variants = {l, l.replace("-", "_"), l.replace("-", ""), base}
    # Heurística adicional: enus -> en-us, ptbr -> pt-br
    if len(l) > 2:
        variants.add(f"{base}-{l[len(base) :]}")
        variants.add(f"{base}_{l[len(base) :]}")
    return list(variants)


def _subtitle_langs_in_entry(entry: dict) -> dict:
    """
    Extrai mapa de idiomas disponíveis: {lang_code: {'type': 'manual'|'auto'}}
    Considera entry['subtitles'] e entry['automatic_captions'].
    """
    available: Dict[str, dict] = {}
    subs = entry.get("subtitles") or {}
    autos = entry.get("automatic_captions") or {}
    for lang_code, tracks in subs.items():
        if tracks:
            available[lang_code.lower()] = {"type": "manual"}
    for lang_code, tracks in autos.items():
        if tracks:
            lc = lang_code.lower()
            if lc not in available:
                available[lc] = {"type": "auto"}
            else:
                # Se já manual, mantemos manual como prioridade
                pass
    return available


def _match_requested_lang(available_langs: dict, requested: list[str]) -> Optional[str]:
    """
    Tenta casar requested (com variantes) com available_langs. Prioriza manual sobre auto.
    Retorna código real presente em available_langs ou None.
    """
    # Ordenar por tipo: manual primeiro
    manual = [k for k, v in available_langs.items() if v["type"] == "manual"]
    auto = [k for k, v in available_langs.items() if v["type"] == "auto"]

    # Gerar todas variantes
    requested_variants: List[List[str]] = [
        _normalize_lang_variants(r) for r in requested
    ]

    def find_in_pool(pool: List[str]) -> Optional[str]:
        pool_l = [p.lower() for p in pool]
        for variants in requested_variants:
            for v in variants:
                for p in pool_l:
                    # Casamento por igualdade ou prefixo base
                    if p == v or p.startswith(v):
                        return p
        return None

    chosen = find_in_pool(manual) or find_in_pool(auto)
    return chosen


def download_playlist(
    playlist_url: str,
    output_dir: str,
    audio_only: bool = False,
    download_subtitles: bool = False,
    subtitle_languages: Optional[list[str]] = None,
    download_delay: int = 5,
    interactive: bool = False,
    checkpoint_manager: Optional[CheckpointManager] = None,
) -> list[dict]:
    """
    Download videos or audio from a YouTube playlist.
    Uses pathlib.Path for cross-platform compatibility.
    """
    # Usa Path para garantir separadores corretos no SO atual
    output_path = Path(output_dir)
    downloads_dir = output_path / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []
    os.makedirs(output_dir, exist_ok=True)

    base_opts = {
        # Usar ID no nome para renomear com precisão depois
        "outtmpl": {
            "default": str(downloads_dir / "%(id)s.%(ext)s"),
            "subtitle": str(downloads_dir / "%(id)s.%(subtitle_language)s.%(ext)s"),
        },
        "ignoreerrors": True,
        "no_warnings": True,
        "quiet": True,
        "extract_flat": False,
        "progress_hooks": [
            lambda d: logger.debug(f"Download progress: {d.get('status', 'unknown')}")
        ],
        "sleep_interval": download_delay,
        "max_sleep_interval": download_delay,
    }

    if audio_only:
        base_opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        )
        logger.info("📻 Modo: somente áudio")
    else:
        base_opts.update(
            {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            }
        )
        logger.info("🎬 Modo: vídeo + áudio")

    if download_subtitles:
        langs = subtitle_languages or ["en", "pt"]
        base_opts.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": langs,
                "subtitlesformat": "srt",
            }
        )
        logger.info(f"📝 Tentando baixar legendas existentes: {', '.join(langs)}")

    try:
        logger.info("🔍 Consultando playlist no YouTube...")
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            if info is None:
                logger.error("❌ Falha ao extrair informações da playlist")
                return downloaded

            entries = info["entries"] if "entries" in info else [info]
            entries = [e for e in entries if e]
            total_videos = len(entries)
            original_entries = list(entries)  # Keep copy for status display

            # Initialize checkpoint
            if checkpoint_manager:
                checkpoint_manager.initialize_playlist(playlist_url, entries)

                # Check for previously completed videos
                progress = checkpoint_manager.get_progress_summary()
                if progress["completed"] > 0:
                    logger.info("=" * 60)
                    logger.info(f"🔄 RETOMANDO DOWNLOAD")
                    logger.info("=" * 60)
                    logger.info(
                        f"✅ Já concluídos: {progress['completed']}/{progress['total']}"
                    )
                    logger.info(f"⏭️  Pulando vídeos já processados...")
                    logger.info("=" * 60)

                    # Filter out completed videos
                    entries = [
                        e
                        for e in entries
                        if not checkpoint_manager.is_video_completed(e.get("id", ""))
                    ]

                    if not entries:
                        logger.info("✅ Todos os vídeos já foram processados!")
                        return downloaded

            # Mapa ID -> nome desejado "<idx>. <título normalizado>"
            id_to_desired: Dict[str, str] = {}

            # Calcular tempo total estimado
            total_duration = sum(e.get("duration", 0) for e in entries)
            total_hours = total_duration // 3600
            total_minutes = (total_duration % 3600) // 60
            total_seconds = total_duration % 60

            # Estimar tempo de processamento (download + delays)
            estimated_download_time = total_videos * 30
            estimated_delay_time = (
                (total_videos - 1) * download_delay if total_videos > 1 else 0
            )
            estimated_total = estimated_download_time + estimated_delay_time
            est_hours = estimated_total // 3600
            est_minutes = (estimated_total % 3600) // 60

            # Exibir prévia da playlist com status
            logger.info("=" * 60)
            logger.info(f"✅ Playlist encontrada: {total_videos} vídeo(s)")
            if checkpoint_manager:
                progress = checkpoint_manager.get_progress_summary()
                if progress["completed"] > 0:
                    logger.info(
                        f"   ✅ Concluídos: {progress['completed']} | ❌ Pendentes: {progress['pending']}"
                    )
            logger.info("=" * 60)

            # Use original_entries to show ALL videos with status
            for idx, entry in enumerate(original_entries, 1):
                title = entry.get("title", "Unknown")
                duration = entry.get("duration", 0)
                duration_str = (
                    f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
                )
                safe_title = _sanitize_base_title(title)
                desired_name = f"{idx}. {safe_title}"
                vid = entry.get("id", str(idx))
                id_to_desired[vid] = desired_name

                # Check if already completed
                status_icon = (
                    "✅"
                    if checkpoint_manager and checkpoint_manager.is_video_completed(vid)
                    else "❌"
                )
                logger.info(f"  {status_icon} {idx}. {title} ({duration_str})")

            logger.info("=" * 60)

            # Exibir resumo de tempo
            if total_hours > 0:
                logger.info(
                    f"⏱️  Duração total: {total_hours}h {total_minutes}m {total_seconds}s"
                )
            else:
                logger.info(f"⏱️  Duração total: {total_minutes}m {total_seconds}s")

            if est_hours > 0:
                logger.info(
                    f"⏳ Tempo estimado de download: ~{est_hours}h {est_minutes}m"
                )
            else:
                logger.info(f"⏳ Tempo estimado de download: ~{est_minutes}m")

            logger.info(f"⏸️  Delay entre downloads: {download_delay}s")

            # Pré-checagem de legendas por vídeo (quando solicitado)
            per_video_lang_choice: Dict[str, List[str]] = {}
            requested_langs = subtitle_languages or []

            if download_subtitles and requested_langs and interactive:
                logger.info("=" * 60)
                logger.info("🔎 Verificando disponibilidade de legendas...")
                logger.info("=" * 60)

                videos_missing_subtitles = []

                for idx, entry in enumerate(entries, 1):
                    title = entry.get("title", f"video_{idx}")
                    video_id = entry.get("id", str(idx))
                    available = _subtitle_langs_in_entry(entry)

                    if not available:
                        videos_missing_subtitles.append((idx, entry, available))
                        per_video_lang_choice[video_id] = []
                        logger.info(f"  ❌ {idx}. {title}: sem legendas")
                        continue

                    # Tentar casar idiomas solicitados com disponíveis
                    chosen_langs: List[str] = []
                    for req in requested_langs:
                        match = _match_requested_lang(available, [req])
                        if match and match not in chosen_langs:
                            chosen_langs.append(match)

                    if chosen_langs:
                        per_video_lang_choice[video_id] = chosen_langs
                        logger.info(
                            f"  ✅ {idx}. {title}: encontrados {', '.join(chosen_langs)}"
                        )
                    else:
                        videos_missing_subtitles.append((idx, entry, available))
                        per_video_lang_choice[video_id] = []
                        logger.info(
                            f"  ⚠️  {idx}. {title}: idiomas solicitados não encontrados"
                        )

                # Prompt interativo para vídeos sem os idiomas solicitados
                if videos_missing_subtitles:
                    logger.info("=" * 60)
                    logger.info(
                        f"⚠️  {len(videos_missing_subtitles)} vídeo(s) sem os idiomas solicitados ({', '.join(requested_langs)})"
                    )
                    resp = input(
                        "❓ Ver idiomas disponíveis e escolher manualmente? (s/n): "
                    )

                    if resp in ["s", "sim", "y", "yes"]:
                        for idx, entry, available in videos_missing_subtitles:
                            title = entry.get("title", f"video_{idx}")
                            video_id = entry.get("id", str(idx))

                            logger.info("=" * 60)
                            logger.info(f"🎥 Vídeo {idx}: {title}")

                            if not available:
                                logger.info(
                                    "  ℹ️  Nenhuma legenda disponível neste vídeo"
                                )
                                use_whisper = (
                                    input("  🤖 Usar transcrição Whisper AI? (s/n): ")
                                    .strip()
                                    .lower()
                                )
                                if use_whisper in ["s", "sim", "y", "yes"]:
                                    per_video_lang_choice[video_id] = ["__WHISPER__"]
                                    logger.info(
                                        "  ✅ Marcado para transcrição via Whisper"
                                    )
                                else:
                                    per_video_lang_choice[video_id] = []
                                    logger.info("  ⏭️  Vídeo será pulado")
                                continue

                            # Mostrar legendas disponíveis
                            manual = [
                                lang
                                for lang, meta in available.items()
                                if meta["type"] == "manual"
                            ]
                            auto = [
                                lang
                                for lang, meta in available.items()
                                if meta["type"] == "auto"
                            ]

                            logger.info(
                                f"  📝 Manuais: {', '.join(manual) if manual else 'nenhuma'}"
                            )
                            logger.info(
                                f"  🤖 Automáticas: {', '.join(auto) if auto else 'nenhuma'}"
                            )

                            sel = input(
                                "  ➡️  Idiomas desejados (ex: pt-BR,en) ou 'whisper': "
                            ).strip()

                            if sel.lower() in ["whisper", "w"]:
                                per_video_lang_choice[video_id] = ["__WHISPER__"]
                                logger.info("  ✅ Marcado para transcrição via Whisper")
                            elif sel:
                                requested = [
                                    s.strip() for s in sel.split(",") if s.strip()
                                ]
                                chosen = []
                                for req in requested:
                                    match = _match_requested_lang(available, [req])
                                    if match and match not in chosen:
                                        chosen.append(match)

                                if chosen:
                                    per_video_lang_choice[video_id] = chosen
                                    logger.info(
                                        f"  ✅ Selecionados: {', '.join(chosen)}"
                                    )
                                else:
                                    logger.warning(
                                        f"  ⚠️  Nenhum idioma válido em '{sel}'"
                                    )
                                    per_video_lang_choice[video_id] = []
                            else:
                                per_video_lang_choice[video_id] = []
                                logger.info("  ⏭️  Nenhum idioma selecionado")
                    else:
                        logger.info("➡️  Usando configuração padrão")

            # Confirmação interativa de prosseguimento
            if interactive:
                logger.info("=" * 60)
                response = (
                    input("▶️  Prosseguir com o download? (s/n): ").strip().lower()
                )
                if response not in ["s", "sim", "y", "yes"]:
                    logger.info("🛑 Download cancelado pelo usuário")
                    return downloaded

            logger.info("=" * 60)
            logger.info(f"⬇️  Iniciando downloads...")
            logger.info("=" * 60)

            # Download sequencial
            for idx, entry in enumerate(entries, 1):
                try:
                    video_url = (
                        entry.get("webpage_url") or entry.get("url") or entry.get("id")
                    )
                    video_title = entry.get("title", "Unknown")
                    video_id = entry.get("id", str(idx))

                    # Find real index in original playlist
                    real_idx = next(
                        (
                            i + 1
                            for i, e in enumerate(original_entries)
                            if e.get("id") == video_id
                        ),
                        idx,
                    )

                    logger.info(
                        f"📥 [{real_idx}/{total_videos}] Baixando: {video_title}"
                    )

                    # Ajustar idiomas de legendas por vídeo
                    local_opts = dict(base_opts)

                    if download_subtitles and video_id in per_video_lang_choice:
                        chosen = per_video_lang_choice[video_id]

                        if "__WHISPER__" in chosen:
                            local_opts.update(
                                {
                                    "writesubtitles": False,
                                    "writeautomaticsub": False,
                                }
                            )
                            logger.debug(
                                f"  🤖 Marcado para Whisper (sem download de legendas)"
                            )
                        elif chosen:
                            local_opts.update(
                                {
                                    "writesubtitles": True,
                                    "writeautomaticsub": True,
                                    "subtitleslangs": chosen,
                                    "subtitlesformat": "srt",
                                }
                            )
                            logger.debug(f"  📝 Baixando legendas: {', '.join(chosen)}")

                    with yt_dlp.YoutubeDL(local_opts) as ydl_single:
                        ydl_single.download([video_url])

                    # Rename downloaded files immediately for this video
                    if video_id in id_to_desired:
                        _rename_downloads_to_desired_names(
                            str(downloads_dir), {video_id: id_to_desired[video_id]}
                        )

                    # Discover subtitle files that were downloaded
                    downloaded_subtitle_files = []
                    if download_subtitles:
                        files = [f for f in downloads_dir.iterdir() if f.is_file()]
                        desired_prefix = id_to_desired.get(video_id, "")
                        for fpath in files:
                            fname = fpath.name
                            if fname.lower().endswith(".srt") and fname.startswith(
                                desired_prefix
                            ):
                                downloaded_subtitle_files.append(fname)

                    logger.info(
                        f"✅ [{real_idx}/{total_videos}] Download concluído: {video_title}"
                    )
                    if downloaded_subtitle_files:
                        logger.debug(
                            f"   📝 Legendas baixadas: {', '.join(downloaded_subtitle_files)}"
                        )

                    # Mark as completed in checkpoint with subtitle files
                    if checkpoint_manager:
                        # Determine subtitle source based on settings
                        sub_source = None
                        if download_subtitles:
                            if video_id in per_video_lang_choice:
                                chosen = per_video_lang_choice[video_id]
                                if "__WHISPER__" in chosen:
                                    sub_source = "whisper_pending"
                                elif chosen and downloaded_subtitle_files:
                                    sub_source = "youtube"

                        checkpoint_manager.mark_video_completed(
                            video_id=video_id,
                            subtitle_source=sub_source,
                            subtitle_files=downloaded_subtitle_files,
                        )

                    if idx < total_videos and download_delay > 0:
                        import time

                        logger.info(f"⏸️  Aguardando {download_delay}s...")
                        time.sleep(download_delay)

                except Exception as e:
                    logger.error(
                        f"❌ [{real_idx}/{total_videos}] Falha: {video_title} - {str(e)[:100]}"
                    )

                    # Mark as failed in checkpoint
                    if checkpoint_manager:
                        checkpoint_manager.mark_video_failed(video_id, str(e)[:500])

                    continue

            # Note: Files are already renamed individually after each download
            # No need to rename all at once here anymore

            # Particionar arquivos baixados
            files = [f for f in downloads_dir.iterdir() if f.is_file()]
            media_files = []
            srt_files = []

            for fpath in files:
                ext = fpath.suffix.lower()
                if ext == ".srt":
                    srt_files.append(fpath.name)
                elif ext in SUPPORTED_MEDIA_EXTS:
                    media_files.append(fpath.name)

            for fname in media_files:
                path = str(downloads_dir / fname)
                stem = Path(fname).stem
                downloaded.append(
                    {"file_path": path, "stem": stem, "subtitles_found": False}
                )

            for item in downloaded:
                prefix = item["stem"]
                related = [s for s in srt_files if s.startswith(prefix)]
                if related:
                    item["subtitles_found"] = True
                    item["subtitle_files"] = [str(downloads_dir / r) for r in related]

            logger.info(f"✅ Arquivos de mídia: {len(downloaded)}")
            logger.info(f"📝 Arquivos de legenda: {len(srt_files)}")
    except Exception as e:
        logger.error(f"❌ Erro no download: {e}")
        raise

    return downloaded


def extract_audio(video_path: str, output_dir: str) -> str:
    """Extract audio from a video file using ffmpeg (no pydub dependency)."""
    os.makedirs(output_dir, exist_ok=True)
    video_name = Path(video_path).stem
    audio_path = os.path.join(output_dir, f"{video_name}.mp3")

    logger.info(f"🎵 Extraindo áudio: {Path(video_path).name}")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "libmp3lame",
        "-qscale:a",
        "4",
        audio_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        logger.info(f"✅ Áudio extraído: {Path(audio_path).name}")
        return audio_path
    except subprocess.CalledProcessError as e:
        logger.error(
            f"❌ Falha na extração de áudio: {e.stderr.decode(errors='ignore')[:300]}"
        )
        raise RuntimeError(f"Failed to extract audio via ffmpeg: {e}")


def convert_audio_to_mono_64kbps(
    audio_path: str, output_dir: str, keep_original: bool = False
) -> str:
    """Convert audio file to mp3 64kbps mono using ffmpeg."""
    if keep_original:
        logger.info(f"✅ Mantendo áudio original: {Path(audio_path).name}")
        return audio_path

    os.makedirs(output_dir, exist_ok=True)
    audio_name = Path(audio_path).stem
    converted_path = str(Path(output_dir) / f"{audio_name}_64kbps_mono.mp3")

    logger.info(f"🔄 Convertendo para 64kbps mono: {Path(audio_path).name}")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-ac",
        "1",
        "-b:a",
        "64k",
        "-vn",
        str(converted_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        logger.info(f"✅ Áudio convertido: {Path(converted_path).name}")
        return converted_path
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Falha na conversão: {e.stderr.decode(errors='ignore')[:300]}")
        raise RuntimeError(f"Failed to convert audio via ffmpeg: {e}")


def process_playlist(
    playlist_url: str,
    output_dir: str,
    api_key: str,
    audio_only: bool = False,
    keep_original_audio: bool = False,
    skip_transcription: bool = False,
    language: Optional[str] = None,
    verbose: bool = False,
    prefer_existing_subtitles: bool = False,
    subtitle_languages: Optional[list[str]] = None,
    download_delay: int = 5,
    interactive: bool = False,
    enable_checkpoint: bool = True,
) -> list[dict]:
    """Process a YouTube playlist: download, extract audio, convert, transcribe, and generate SRT."""
    results = []

    downloads_dir = os.path.join(output_dir, "downloads")
    audio_dir = os.path.join(output_dir, "audio")
    converted_dir = os.path.join(output_dir, "converted")
    srt_dir = os.path.join(output_dir, "subtitles")

    for directory in [downloads_dir, audio_dir, converted_dir, srt_dir]:
        os.makedirs(directory, exist_ok=True)

    # Initialize checkpoint manager
    checkpoint = None
    if enable_checkpoint:
        checkpoint_path = get_checkpoint_path(output_dir, playlist_url)
        checkpoint = CheckpointManager(checkpoint_path)

    try:
        logger.info("=" * 60)
        logger.info("📋 ETAPA 1: Download da Playlist")
        logger.info("=" * 60)

        downloaded_items = download_playlist(
            playlist_url,
            output_dir,
            audio_only=audio_only,
            download_subtitles=prefer_existing_subtitles,
            subtitle_languages=subtitle_languages,
            download_delay=download_delay,
            interactive=interactive,
            checkpoint_manager=checkpoint,
        )

        if not downloaded_items:
            logger.warning("⚠️  Nenhum arquivo foi baixado")
            return results

        total_items = len(downloaded_items)

        for idx, item in enumerate(downloaded_items, 1):
            file_path = item["file_path"]
            file_name = Path(file_path).stem

            logger.info("=" * 60)
            logger.info(f"🎬 PROCESSANDO [{idx}/{total_items}]: {file_name}")
            logger.info("=" * 60)

            result = {
                "original_file": file_path,
                "audio_file": None,
                "converted_file": None,
                "srt_file": None,
                "status": "pending",
                "used_existing_subtitles": False,
                "used_whisper": False,
            }

            try:
                # Copiar legendas existentes para srt_dir (mesmo com skip_transcription)
                has_existing_subs = prefer_existing_subtitles and item.get(
                    "subtitles_found"
                )

                if has_existing_subs:
                    logger.info("📝 Copiando legendas existentes...")
                    srt_files = item["subtitle_files"]
                    copied_srts = []

                    for src in srt_files:
                        src_name = Path(src).name
                        dst = os.path.join(srt_dir, src_name)
                        shutil.copyfile(src, dst)
                        copied_srts.append(dst)
                        logger.info(f"  ✅ Copiada: {src_name}")

                    result["used_existing_subtitles"] = True
                    result["subtitle_files_copied"] = copied_srts
                    logger.info(f"✅ Legendas copiadas: {len(copied_srts)} arquivo(s)")

                # Verificar se precisa de Whisper (só se não tiver legendas e transcrição habilitada)
                needs_whisper = not skip_transcription and not has_existing_subs

                # Processamento de transcrição
                if not skip_transcription:
                    logger.info("📝 ETAPA 2: Geração de Legendas")

                    if has_existing_subs:
                        # Selecionar legenda principal baseada no idioma preferido
                        chosen = None
                        if subtitle_languages:
                            variants_list = [
                                _normalize_lang_variants(lg)
                                for lg in subtitle_languages
                            ]

                            def matches_lang(fname: str, variants: list[str]) -> bool:
                                name = Path(fname).name.lower()
                                return any(
                                    (f".{v}.srt" in name) or (f".{v}." in name)
                                    for v in variants
                                )

                            manual = [
                                f
                                for f in copied_srts
                                if ".auto." not in Path(f).name.lower()
                            ]
                            auto = [
                                f
                                for f in copied_srts
                                if ".auto." in Path(f).name.lower()
                            ]
                            for variants in variants_list:
                                for sf in manual:
                                    if matches_lang(sf, variants):
                                        chosen = sf
                                        break
                                if chosen:
                                    break
                                for sf in auto:
                                    if matches_lang(sf, variants):
                                        chosen = sf
                                        break
                                if chosen:
                                    break

                        chosen = chosen or (copied_srts[0] if copied_srts else None)

                        result["srt_file"] = chosen
                        result["used_whisper"] = False
                        if chosen:
                            logger.info(f"📌 Legenda principal: {Path(chosen).name}")
                        logger.info(
                            "⏭️  Pulando extração/conversão de áudio (não necessário)"
                        )
                    else:
                        # Precisa do Whisper: extrair e converter áudio
                        logger.info(
                            "🤖 Legendas não encontradas, preparando para Whisper..."
                        )

                        # Step 2: Audio extraction
                        if audio_only:
                            audio_path = file_path
                            logger.info("✅ Usando arquivo de áudio direto")
                        else:
                            logger.info("🎵 ETAPA 2.1: Extração de Áudio")
                            audio_path = extract_audio(file_path, audio_dir)
                        result["audio_file"] = audio_path

                        # Step 3: Convert
                        logger.info("🔄 ETAPA 2.2: Conversão de Áudio")
                        converted_path = convert_audio_to_mono_64kbps(
                            audio_path, converted_dir, keep_original=keep_original_audio
                        )
                        result["converted_file"] = converted_path

                        # Transcribe
                        logger.info("🤖 Enviando para OpenAI Whisper...")
                        srt_path = os.path.join(srt_dir, f"{file_name}.whisper.srt")
                        transcribe_audio_to_srt(
                            audio_path=converted_path,
                            output_path=srt_path,
                            api_key=api_key,
                            language=language,
                            verbose=verbose,
                        )
                        result["srt_file"] = srt_path
                        result["used_whisper"] = True
                        result["used_existing_subtitles"] = False
                        logger.info(f"✅ Transcrição salva: {Path(srt_path).name}")
                else:
                    logger.info("⏭️  Transcrição desabilitada (--skip-transcription)")

                result["status"] = "success"
                logger.info(f"✅ Processamento concluído: {file_name}")

            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
                logger.error(f"❌ Falha no processamento: {str(e)[:200]}")

            results.append(result)

        return results
    except Exception as e:
        logger.error(f"❌ Erro fatal no processamento: {e}")
        raise


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="YouTube Playlist Summary Tool - Download, transcribe, and generate subtitles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download and transcribe a playlist (uses existing subtitles if available)
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..."

  # Download audio only
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --audio-only

  # Keep original audio format (no conversion)
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --keep-original

  # Specify language for transcription
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --language pt

  # Skip transcription (download and convert only)
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --skip-transcription

  # Interactive mode with confirmation prompt
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --interactive

  # Disable study material generation
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --no-study-material

  # Force Whisper transcription (ignore existing subtitles)
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --no-prefer-existing-subtitles
        """,
    )

    parser.add_argument(
        "-u",
        "--url",
        type=str,
        required=True,
        help="YouTube playlist URL or single video URL",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="./output",
        help="Output directory (default: ./output)",
    )

    parser.add_argument(
        "-k",
        "--api-key",
        type=str,
        default=os.environ.get("OPENAI_API_KEY"),
        help="OpenAI API key (can also be set via OPENAI_API_KEY environment variable)",
    )

    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default=None,
        help="Language code for transcription (e.g., en, pt, es). If not specified, auto-detect will be used",
    )

    parser.add_argument(
        "-a", "--audio-only", action="store_true", help="Download only audio (no video)"
    )

    parser.add_argument(
        "--keep-original",
        action="store_true",
        help="Keep original audio format (do not convert to 64kbps mono)",
    )

    parser.add_argument(
        "--skip-transcription",
        action="store_true",
        help="Skip transcription step (download and convert only)",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    # Changed: prefer-existing-subtitles agora é True por padrão
    parser.add_argument(
        "--no-prefer-existing-subtitles",
        action="store_true",
        help="Desabilitar busca de legendas existentes do YouTube (forçar uso do Whisper)",
    )

    parser.add_argument(
        "--subtitle-languages",
        type=str,
        default="pt-BR,en",
        help='Lista de idiomas para buscar legendas existentes (default: "pt-BR,en")',
    )

    parser.add_argument(
        "--download-delay",
        type=int,
        default=5,
        help="Delay em segundos entre downloads de vídeos para evitar rate-limiting (default: 5s)",
    )

    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Modo interativo: exibe prévia da playlist e aguarda confirmação antes de iniciar",
    )

    parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Desabilitar sistema de checkpoint/retomada (força reprocessamento completo)",
    )

    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Limpar checkpoint existente e reiniciar do zero",
    )

    # Novo: geração de material de estudo (habilitado por padrão)
    parser.add_argument(
        "--no-study-material",
        action="store_true",
        help="Desabilitar geração automática de material de estudo após processamento",
    )

    # Language options for study material
    default_source = ",".join(get_default_source_languages())
    default_output = get_default_output_language()

    parser.add_argument(
        "--source-language",
        type=str,
        default=default_source,
        help=f"Idioma(s) de origem das legendas para material de estudo, separados por vírgula em ordem de prioridade (default: {default_source})",
    )

    parser.add_argument(
        "--study-language",
        type=str,
        default=default_output,
        help=f"Idioma de saída do material de estudo (default: {default_output})",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_arguments()
    setup_logging(args.verbose)

    logger.info("=" * 60)
    logger.info("🎬 YouTube Playlist Summary Tool")
    logger.info("=" * 60)

    # Derivar prefer_existing_subtitles da flag negada
    prefer_existing_subtitles = not args.no_prefer_existing_subtitles

    # Derivar generate_study_material da flag negada
    generate_study_material = not args.no_study_material

    if not args.skip_transcription and not args.api_key:
        logger.error("❌ Chave OpenAI necessária para transcrição")
        logger.error("   Use --api-key ou OPENAI_API_KEY")
        logger.error("   Ou use --skip-transcription")
        return 1

    # Handle checkpoint clearing
    if args.clear_checkpoint:
        checkpoint_path = get_checkpoint_path(args.output, args.url)
        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
            logger.info(f"🗑️  Checkpoint removido: {checkpoint_path}")
        else:
            logger.info("ℹ️  Nenhum checkpoint encontrado para remover")

    # Parse subtitle languages - Created by Rodgui (rod.gui@gmail.com / @rodgui on GitHub)
    subtitle_langs = (
        args.subtitle_languages.split(",")
        if args.subtitle_languages
        else ["pt-BR", "en"]
    )

    logger.info(f"🔗 URL: {args.url}")
    logger.info(f"📁 Diretório de saída: {args.output}")
    logger.info(f"🎵 Somente áudio: {args.audio_only}")
    logger.info(f"💾 Manter áudio original: {args.keep_original}")
    logger.info(f"🌍 Idioma transcrição: {args.language or 'auto-detect'}")
    logger.info(f"⏭️  Pular transcrição: {args.skip_transcription}")
    logger.info(f"📝 Preferir legendas existentes: {prefer_existing_subtitles}")
    logger.info(f"🌐 Idiomas legendas: {', '.join(subtitle_langs)}")
    logger.info(f"⏸️  Delay: {args.download_delay}s")
    logger.info(f"🤝 Modo interativo: {args.interactive}")
    logger.info(
        f"📖 Checkpoint: {'desabilitado' if args.no_checkpoint else 'habilitado'}"
    )
    logger.info(
        f"📚 Material de estudo: {'desabilitado' if args.no_study_material else 'habilitado'}"
    )
    if not args.no_study_material:
        logger.info(f"   🔤 Idioma(s) origem: {args.source_language}")
        logger.info(f"   🎯 Idioma saída: {args.study_language}")

    try:
        results = process_playlist(
            playlist_url=args.url,
            output_dir=args.output,
            api_key=args.api_key or "",
            audio_only=args.audio_only,
            keep_original_audio=args.keep_original,
            skip_transcription=args.skip_transcription,
            language=args.language,
            verbose=args.verbose,
            prefer_existing_subtitles=prefer_existing_subtitles,
            subtitle_languages=subtitle_langs,
            download_delay=args.download_delay,
            interactive=args.interactive,
            enable_checkpoint=not args.no_checkpoint,
        )

        logger.info("=" * 60)
        logger.info("📊 RESUMO DO PROCESSAMENTO")
        logger.info("=" * 60)

        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")
        whisper_count = sum(1 for r in results if r.get("used_whisper", False))
        existing_subs_count = sum(
            1 for r in results if r.get("used_existing_subtitles", False)
        )

        logger.info(f"📝 Total processado: {len(results)}")
        logger.info(f"✅ Sucesso: {success_count}")
        logger.info(f"❌ Erros: {error_count}")
        logger.info(f"🤖 Transcritos via Whisper: {whisper_count}")
        logger.info(f"📋 Legendas existentes usadas: {existing_subs_count}")

        if error_count > 0:
            logger.warning("⚠️  Alguns arquivos falharam:")
            for r in results:
                if r["status"] == "error":
                    logger.warning(
                        f"  • {Path(r['original_file']).name}: {r.get('error', 'Unknown')[:100]}"
                    )

        # Geração de material de estudo (se habilitado e houver legendas)
        if (
            generate_study_material
            and not args.skip_transcription
            and success_count > 0
        ):
            logger.info("=" * 60)
            logger.info("📚 ETAPA FINAL: Geração de Material de Estudo")
            logger.info("=" * 60)

            subtitle_dir = os.path.join(args.output, "subtitles")

            # Verificar se há arquivos de legenda
            srt_files = (
                [f for f in os.listdir(subtitle_dir) if f.endswith(".srt")]
                if os.path.isdir(subtitle_dir)
                else []
            )

            if srt_files:
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                study_output = os.path.join(
                    args.output, f"study_material_{timestamp}.md"
                )

                # Parse source languages
                source_languages = parse_language_list(args.source_language)

                try:
                    generate_playlist_study_content(
                        subtitle_dir=subtitle_dir,
                        output_path=study_output,
                        api_key=args.api_key or "",
                        study_language=args.study_language,
                        source_languages=source_languages,
                        skip_gpt=False,
                        interactive=args.interactive,
                    )
                    logger.info(f"✅ Material de estudo gerado: {study_output}")
                except Exception as e:
                    logger.error(f"❌ Falha na geração do material de estudo: {e}")
            else:
                logger.warning(
                    "⚠️  Nenhuma legenda encontrada para gerar material de estudo"
                )
        elif generate_study_material and args.skip_transcription:
            logger.info("⏭️  Material de estudo não gerado (transcrição desabilitada)")

        logger.info("=" * 60)
        logger.info("✨ Concluído!")
        logger.info("=" * 60)

        return 0 if error_count == 0 else 1

    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
