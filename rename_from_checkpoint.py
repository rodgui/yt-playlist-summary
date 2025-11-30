#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rename Files from Checkpoint

Script para renomear arquivos de vídeo e legendas baseado no checkpoint JSON.
Útil para corrigir arquivos que foram baixados com video_id ao invés do título.
"""

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import re


def _sanitize_base_title(title: str) -> str:
    r"""
    Normaliza o título mantendo ':' e removendo caracteres problemáticos.
    Substitui / e \ por ' - ' e comprime espaços.
    """
    t = (title or '').replace('：', ':')  # converte dois-pontos "fullwidth" para ':'
    t = t.replace('/', ' - ').replace('\\', ' - ')
    # remove caracteres geralmente problemáticos, mantendo ':'
    t = re.sub(r'[<>\"|\?\*]', '', t)
    # comprime espaços
    t = re.sub(r'\s{2,}', ' ', t).strip()
    return t


def _ensure_unique_path(path: str) -> str:
    """Garante nome único adicionando sufixo (n) se já existir."""
    if not os.path.exists(path):
        return path
    base = Path(path).with_suffix('')
    ext = Path(path).suffix
    n = 1
    while True:
        candidate = f"{base} ({n}){ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def load_checkpoint(checkpoint_path: str) -> Dict:
    """Carrega dados do checkpoint JSON."""
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint não encontrado: {checkpoint_path}")
    
    with open(checkpoint_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_rename_map(checkpoint_data: Dict) -> Dict[str, str]:
    """
    Constrói mapa de video_id -> nome desejado baseado no checkpoint.
    
    Returns:
        Dict mapeando video_id para "<index>. <título sanitizado>"
    """
    videos = checkpoint_data.get('videos', {})
    rename_map = {}
    
    for video_id, video_info in videos.items():
        index = video_info.get('index', 0)
        title = video_info.get('title', 'Unknown')
        safe_title = _sanitize_base_title(title)
        desired_name = f"{index}. {safe_title}"
        rename_map[video_id] = desired_name
    
    return rename_map


def rename_files_in_directory(
    directory: str,
    rename_map: Dict[str, str],
    dry_run: bool = False,
    verbose: bool = False
) -> tuple[int, int]:
    """
    Renomeia arquivos em um diretório baseado no mapa.
    
    Args:
        directory: Diretório contendo os arquivos
        rename_map: Mapa de video_id -> nome desejado
        dry_run: Se True, apenas mostra o que seria feito
        verbose: Exibe detalhes de cada operação
        
    Returns:
        Tupla (renamed_count, skipped_count)
    """
    if not os.path.isdir(directory):
        print(f"⚠️  Diretório não encontrado: {directory}")
        return 0, 0
    
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    renamed_count = 0
    skipped_count = 0
    
    print(f"\n📁 Processando: {directory}")
    print(f"   Total de arquivos: {len(files)}")
    
    for fname in files:
        # Verificar se o arquivo começa com algum video_id conhecido
        matched_id = None
        for video_id in rename_map.keys():
            if fname.startswith(video_id + "."):
                matched_id = video_id
                break
        
        if not matched_id:
            if verbose:
                print(f"   ⏭️  Pulando (não é video_id): {fname}")
            skipped_count += 1
            continue
        
        # Extrair extensão/sufixo (ex: .mp4, .pt-BR.srt, .en.srt)
        rest = fname[len(matched_id):]  # começa com '.'
        
        desired_base = rename_map[matched_id]
        new_name = f"{desired_base}{rest}"
        
        old_path = os.path.join(directory, fname)
        new_path = os.path.join(directory, new_name)
        new_path = _ensure_unique_path(new_path)
        
        if dry_run:
            print(f"   🔄 {fname}")
            print(f"      → {Path(new_path).name}")
        else:
            try:
                os.rename(old_path, new_path)
                renamed_count += 1
                if verbose:
                    print(f"   ✅ {fname} → {Path(new_path).name}")
            except Exception as e:
                print(f"   ❌ Erro ao renomear {fname}: {e}")
                skipped_count += 1
                continue
    
    return renamed_count, skipped_count


def main():
    parser = argparse.ArgumentParser(
        description='Renomeia arquivos de vídeo e legendas usando checkpoint JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Dry-run (visualizar mudanças sem executar)
  %(prog)s --checkpoint output/.checkpoint_abc123.json --dry-run

  # Renomear downloads e subtitles
  %(prog)s --checkpoint output/.checkpoint_abc123.json

  # Renomear apenas downloads
  %(prog)s --checkpoint output/.checkpoint_abc123.json --downloads-only

  # Modo verbose
  %(prog)s -c output/.checkpoint_abc123.json -v
        """
    )
    
    parser.add_argument(
        '-c', '--checkpoint',
        type=str,
        required=True,
        help='Caminho para o arquivo checkpoint JSON'
    )
    
    parser.add_argument(
        '-d', '--downloads-dir',
        type=str,
        default=None,
        help='Diretório de downloads (default: inferido do checkpoint)'
    )
    
    parser.add_argument(
        '-s', '--subtitles-dir',
        type=str,
        default=None,
        help='Diretório de legendas (default: inferido do checkpoint)'
    )
    
    parser.add_argument(
        '--downloads-only',
        action='store_true',
        help='Renomear apenas arquivos de download'
    )
    
    parser.add_argument(
        '--subtitles-only',
        action='store_true',
        help='Renomear apenas arquivos de legendas'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mostrar o que seria feito sem executar as mudanças'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Exibir detalhes de cada operação'
    )
    
    args = parser.parse_args()
    
    # Load checkpoint
    try:
        print("=" * 60)
        print("🔄 RENOMEANDO ARQUIVOS A PARTIR DO CHECKPOINT")
        print("=" * 60)
        print(f"📖 Carregando checkpoint: {args.checkpoint}")
        
        checkpoint_data = load_checkpoint(args.checkpoint)
        total_videos = checkpoint_data.get('total_videos', 0)
        print(f"✅ Checkpoint carregado: {total_videos} vídeo(s)")
        
    except Exception as e:
        print(f"❌ Erro ao carregar checkpoint: {e}")
        return 1
    
    # Build rename map
    rename_map = build_rename_map(checkpoint_data)
    print(f"📋 Mapeamento criado: {len(rename_map)} video_id(s)")
    
    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN: Nenhum arquivo será modificado")
    
    # Infer directories if not provided
    checkpoint_dir = Path(args.checkpoint).parent
    downloads_dir = args.downloads_dir or os.path.join(checkpoint_dir, 'downloads')
    subtitles_dir = args.subtitles_dir or os.path.join(checkpoint_dir, 'subtitles')
    
    total_renamed = 0
    total_skipped = 0
    
    # Rename downloads
    if not args.subtitles_only:
        renamed, skipped = rename_files_in_directory(
            downloads_dir,
            rename_map,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        total_renamed += renamed
        total_skipped += skipped
        
        if not args.dry_run:
            print(f"   ✅ Renomeados: {renamed}")
            print(f"   ⏭️  Pulados: {skipped}")
    
    # Rename subtitles
    if not args.downloads_only:
        renamed, skipped = rename_files_in_directory(
            subtitles_dir,
            rename_map,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        total_renamed += renamed
        total_skipped += skipped
        
        if not args.dry_run:
            print(f"   ✅ Renomeados: {renamed}")
            print(f"   ⏭️  Pulados: {skipped}")
    
    # Summary
    print("\n" + "=" * 60)
    if args.dry_run:
        print("📊 RESUMO (DRY-RUN)")
        print(f"   Seriam renomeados: {total_renamed}")
        print(f"   Seriam pulados: {total_skipped}")
        print("\n💡 Execute sem --dry-run para aplicar as mudanças")
    else:
        print("📊 RESUMO")
        print(f"   ✅ Total renomeados: {total_renamed}")
        print(f"   ⏭️  Total pulados: {total_skipped}")
        print("\n✨ Concluído!")
    print("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
