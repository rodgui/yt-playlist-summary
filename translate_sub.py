#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import sys
from pathlib import Path
import logging
from typing import List, Tuple

from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("translate_sub")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Traduz um arquivo .srt usando GPT-4.1-mini",
        epilog="""
Exemplos:
  python translate_sub.py --input ./output/subtitles/video.pt-BR.srt --source pt-BR --target en
  python translate_sub.py -i legenda.srt -s en -t pt
        """
    )
    parser.add_argument("-i", "--input", type=str, required=True, help="Caminho do arquivo .srt")
    parser.add_argument("-s", "--source", type=str, required=True, help="Idioma original (ex: pt, pt-BR, en)")
    parser.add_argument("-t", "--target", type=str, required=True, help="Idioma desejado (ex: en, pt-BR)")
    parser.add_argument("-k", "--api-key", type=str, default=os.environ.get("OPENAI_API_KEY"),
                        help="Chave OpenAI (ou defina OPENAI_API_KEY)")
    parser.add_argument("--batch-size", type=int, default=150, help="Máx. linhas SRT por lote (default: 150)")
    parser.add_argument("--dry-run", action="store_true", help="Não grava arquivo, apenas simula e exibe amostra")
    return parser.parse_args()

def read_srt_lines(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()

def write_srt_lines(path: Path, lines: List[str]) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def chunk_srt(lines: List[str], batch_size: int) -> List[List[str]]:
    # Lotes por número de linhas para manter timestamps e índices agrupados
    chunks = []
    cur = []
    for line in lines:
        cur.append(line)
        if len(cur) >= batch_size:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks

def build_prompt(source_lang: str, target_lang: str, srt_chunk_text: str) -> str:
    return (
        "Você é um tradutor de legendas SRT. Traduza apenas o texto das legendas mantendo:\n"
        "- índices numéricos\n"
        "- timestamps no formato HH:MM:SS,mmm --> HH:MM:SS,mmm\n"
        "- linhas em branco entre blocos\n"
        "Não adicione comentários, não altere timestamps, não mude a numeração.\n"
        f"Idioma de origem: {source_lang}\n"
        f"Idioma de destino: {target_lang}\n\n"
        "Entrada SRT (traduzir apenas o conteúdo textual, preserve índices e timestamps):\n\n"
        f"{srt_chunk_text}\n\n"
        "Saída SRT traduzida (mesmo formato):"
    )

def translate_chunk(client: OpenAI, model: str, source_lang: str, target_lang: str, chunk_lines: List[str]) -> List[str]:
    chunk_text = "\n".join(chunk_lines)
    prompt = build_prompt(source_lang, target_lang, chunk_text)

    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": "Você traduz legendas SRT mantendo estrutura e timestamps."},
            {"role": "user", "content": prompt},
        ]
    )
    out = resp.choices[0].message.content or ""
    # Remover blocos markdown se retornados
    out = out.strip()
    if out.startswith("```"):
        out = out.split("```")[-2] if "```" in out else out
    return out.splitlines()

def main() -> int:
    args = parse_args()
    if not args.api_key:
        logger.error("OPENAI_API_KEY não definida. Use --api-key ou defina variável de ambiente.")
        return 1

    input_path = Path(args.input)
    if not input_path.exists() or input_path.suffix.lower() != ".srt":
        logger.error("Arquivo de entrada inválido. Forneça um .srt existente.")
        return 1

    target_suffix = args.target.replace(" ", "").replace("/", "_")
    output_path = input_path.with_name(f"{input_path.stem}.translated.{target_suffix}.srt")

    logger.info(f"Arquivo de entrada: {input_path}")
    logger.info(f"Idioma origem: {args.source} | destino: {args.target}")
    logger.info(f"Tamanho do lote: {args.batch_size}")

    lines = read_srt_lines(input_path)
    chunks = chunk_srt(lines, args.batch_size)
    logger.info(f"Chunks gerados: {len(chunks)}")

    client = OpenAI(api_key=args.api_key)
    model = "gpt-4.1-mini"

    translated_all: List[str] = []
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"Traduzindo chunk {i}/{len(chunks)}...")
        try:
            translated = translate_chunk(client, model, args.source, args.target, chunk)
            translated_all.extend(translated)
            # Garantir quebra entre chunks
            if translated and translated[-1].strip() != "":
                translated_all.append("")
        except Exception as e:
            logger.error(f"Falha ao traduzir chunk {i}: {e}")
            return 1

    if args.dry_run:
        logger.info("Dry-run: exibindo primeiras 30 linhas traduzidas:")
        for line in translated_all[:30]:
            print(line)
        return 0

    write_srt_lines(output_path, translated_all)
    logger.info(f"Legenda traduzida salva: {output_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())