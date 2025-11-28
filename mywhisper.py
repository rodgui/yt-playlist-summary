#!/usr/bin/env python3
"""
Audio to SRT Transcriber using OpenAI Whisper API
Converts audio files (MP3, M4A, WAV, FLAC, OGG, WEBM) to SRT subtitles with timestamp synchronization.
"""

import os
import sys
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

from dotenv import load_dotenv
from openai import OpenAI
import subprocess
import csv

# Constants
SUPPORTED_FORMATS = ['.mp3', '.m4a', '.wav', '.flac', '.ogg', '.webm']
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB in bytes
DEFAULT_CHUNK_DURATION = 10  # minutes
TEMP_DIR = Path('temp_chunks')
CACHE_DIR = Path('.cache')


def setup_logging(verbose: bool) -> logging.Logger:
    """Configure logging based on verbose flag."""
    logger = logging.getLogger('whisper_transcriber')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Transcribe audio files to SRT subtitles using OpenAI Whisper API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input audio.mp3
  %(prog)s --input audio.m4a --output subtitles.srt
  %(prog)s --input audio.mp3 --language pt --verbose
  %(prog)s --input audio.wav --chunk-duration 5 --clear-cache
  %(prog)s --input audio_pt.mp3 --translate en  # Translate to English
  %(prog)s --only-translation subtitles.srt --translate pt  # Translate existing SRT
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        required=False,
        type=str,
        default=None,
        help='Path to the input audio file (MP3, M4A, WAV, FLAC, OGG, WEBM)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Path to the output SRT file (default: same as input with .srt extension)'
    )
    
    parser.add_argument(
        '--language', '-l',
        type=str,
        default=None,
        help='Language code for transcription (e.g., en, pt, es). If not specified, auto-detect will be used'
    )
    
    parser.add_argument(
        '--translate', '-t',
        type=str,
        default=None,
        help='Translate the transcription to this language (e.g., en, pt, es). If specified, audio will be transcribed and translated'
    )
    
    parser.add_argument(
        '--only-translation',
        type=str,
        default=None,
        metavar='SRT_FILE',
        help='Translate an existing SRT file to the language specified in --translate (no audio processing)'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='OpenAI API key (default: loaded from .env file)'
    )
    
    parser.add_argument(
        '--chunk-duration',
        type=int,
        default=DEFAULT_CHUNK_DURATION,
        help=f'Duration of each chunk in minutes for large files (default: {DEFAULT_CHUNK_DURATION})'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear cache and force reprocessing of all chunks'
    )

    parser.add_argument(
        '--translation-format',
        type=str,
        choices=['json', 'csv'],
        default='json',
        help='Format used when translating SRT via --only-translation (json|csv). Default: json'
    )
    
    return parser.parse_args()


def validate_audio_file(file_path: str, logger: logging.Logger) -> Path:
    """Validate the input audio file."""
    logger.info("Validating input file...")
    
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")
    
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported file format: {path.suffix}. "
            f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )
    
    logger.info(f"✓ File validated: {path.name}")
    return path


def get_file_hash(file_path: Path) -> str:
    """Generate MD5 hash of file for cache identification."""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_audio_duration(file_path: Path, logger: logging.Logger) -> float:
    """Get audio duration in seconds using ffprobe."""
    logger.info("Loading audio file...")
    
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration_seconds = float(result.stdout.strip())
        duration_minutes = duration_seconds / 60
        logger.info(f"✓ Audio loaded: {duration_minutes:.2f} minutes")
        return duration_seconds
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get audio duration. Is FFmpeg installed? Error: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load audio file: {e}")


def split_audio_into_chunks(
    audio_duration: float,
    file_path: Path,
    chunk_duration_minutes: int,
    logger: logging.Logger
) -> List[Path]:
    """Split audio into chunks if needed using ffmpeg."""
    file_size = file_path.stat().st_size
    
    if file_size <= MAX_FILE_SIZE:
        logger.info(f"File size ({file_size / 1024 / 1024:.2f}MB) is within limit. No splitting needed.")
        return [file_path]
    
    logger.info(f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds 25MB limit. Splitting into chunks...")
    
    # Create temp directory
    TEMP_DIR.mkdir(exist_ok=True)
    
    chunk_duration_seconds = chunk_duration_minutes * 60
    num_chunks = int((audio_duration + chunk_duration_seconds - 1) // chunk_duration_seconds)
    
    logger.info(f"Creating {num_chunks} chunks of {chunk_duration_minutes} minutes each...")
    
    chunks = []
    for i in range(num_chunks):
        start_time = i * chunk_duration_seconds
        chunk_path = TEMP_DIR / f"chunk_{i:04d}{file_path.suffix}"
        
        try:
            cmd = [
                'ffmpeg',
                '-i', str(file_path),
                '-ss', str(start_time),
                '-t', str(chunk_duration_seconds),
                '-c', 'copy',
                '-y',  # Overwrite output file
                str(chunk_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            chunks.append(chunk_path)
            logger.debug(f"  Chunk {i+1}/{num_chunks}: {chunk_path.name}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to split audio chunk {i+1}: {e}")
    
    logger.info(f"✓ Created {len(chunks)} chunks")
    return chunks


def get_cache_path(file_hash: str, chunk_index: int) -> Path:
    """Get cache file path for a specific chunk."""
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{file_hash}_chunk_{chunk_index:04d}.json"


def load_cached_transcription(cache_path: Path, logger: logging.Logger) -> Optional[Dict]:
    """Load transcription from cache if available."""
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"  Cache hit: {cache_path.name}")
            return data
        except Exception as e:
            logger.warning(f"  Failed to load cache {cache_path.name}: {e}")
    return None


def save_transcription_to_cache(cache_path: Path, transcription: Dict, logger: logging.Logger) -> None:
    """Save transcription to cache."""
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(transcription, f, ensure_ascii=False, indent=2)
        logger.debug(f"  Cached: {cache_path.name}")
    except Exception as e:
        logger.warning(f"  Failed to cache transcription: {e}")


def transcribe_chunk(
    client: OpenAI,
    chunk_path: Path,
    language: Optional[str],
    translate_to: Optional[str],
    logger: logging.Logger
) -> Dict:
    """Transcribe a single audio chunk using Whisper API."""
    logger.debug(f"  Uploading {chunk_path.name} to Whisper API...")
    
    try:
        with open(chunk_path, 'rb') as audio_file:
            # If translation is requested, use translations endpoint
            if translate_to:
                logger.debug(f"  Translating to {translate_to}...")
                response = client.audio.translations.create(
                    file=audio_file,
                    model='whisper-1',
                    response_format='verbose_json'
                )
            else:
                # Regular transcription
                params = {
                    'file': audio_file,
                    'model': 'whisper-1',
                    'response_format': 'verbose_json',
                    'timestamp_granularities': ['segment']
                }
                
                if language:
                    params['language'] = language
                
                response = client.audio.transcriptions.create(**params)
        
        logger.debug(f"  ✓ {'Translation' if translate_to else 'Transcription'} completed for {chunk_path.name}")
        return response.model_dump()
    
    except Exception as e:
        raise RuntimeError(f"Whisper API error for {chunk_path.name}: {e}")


def transcribe_audio(
    chunks: List[Path],
    api_key: str,
    language: Optional[str],
    translate_to: Optional[str],
    file_hash: str,
    clear_cache: bool,
    logger: logging.Logger
) -> List[Dict]:
    """Transcribe all audio chunks with caching."""
    client = OpenAI(api_key=api_key)
    transcriptions = []
    
    action = "Translating" if translate_to else "Transcribing"
    logger.info(f"{action} {len(chunks)} chunk(s)...")
    
    if clear_cache and CACHE_DIR.exists():
        logger.info("Clearing cache...")
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(exist_ok=True)
    
    for i, chunk_path in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
        
        # Check cache
        cache_path = get_cache_path(file_hash, i)
        cached = load_cached_transcription(cache_path, logger)
        
        if cached and not clear_cache:
            logger.info(f"  Using cached {action.lower()}")
            transcriptions.append(cached)
        else:
            # Transcribe or translate
            transcription = transcribe_chunk(client, chunk_path, language, translate_to, logger)
            transcriptions.append(transcription)
            
            # Save to cache
            save_transcription_to_cache(cache_path, transcription, logger)
    
    logger.info(f"✓ All chunks {action.lower()}")
    return transcriptions


def format_timestamp(seconds: float) -> str:
    """Format timestamp for SRT format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def parse_srt_file(srt_path: Path, logger: logging.Logger) -> List[Dict[str, str]]:
    """Parse SRT file and extract subtitles with timestamps."""
    logger.info(f"Reading SRT file: {srt_path.name}")
    
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise RuntimeError(f"Failed to read SRT file: {e}")
    
    subtitles = []
    blocks = content.strip().split('\n\n')
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            index = lines[0]
            timestamp = lines[1]
            text = '\n'.join(lines[2:])
            subtitles.append({
                'index': index,
                'timestamp': timestamp,
                'text': text
            })
    
    logger.info(f"✓ Parsed {len(subtitles)} subtitles")
    return subtitles


def quality_check_translations(subtitles: List[Dict[str, str]], target_language: str, logger: logging.Logger) -> Dict[str, int]:
    """Perform quality check on translated subtitles."""
    logger.info("Running quality check on translations...")
    
    issues = {
        'empty_translations': 0,
        'untranslated_markers': 0,
        'encoding_errors': 0,
        'suspicious_length': 0
    }
    
    for sub in subtitles:
        text = sub['text']
        
        # Check for empty translations
        if not text or text.strip() == '':
            issues['empty_translations'] += 1
            logger.debug(f"  Empty translation at subtitle {sub['index']}")
        
        # Check for untranslated markers (common in failed translations)
        untranslated_markers = ['[UNTRANSLATED]', '[ERROR]', '[N/A]', '???']
        if any(marker in text for marker in untranslated_markers):
            issues['untranslated_markers'] += 1
            logger.debug(f"  Untranslated marker at subtitle {sub['index']}: {text[:50]}")
        
        # Check for encoding errors (common Unicode issues)
        try:
            text.encode('utf-8')
        except UnicodeEncodeError:
            issues['encoding_errors'] += 1
            logger.debug(f"  Encoding error at subtitle {sub['index']}")
        
        # Check for suspicious length changes (translation much shorter/longer than typical)
        # Typical translation length ratio is 0.7-1.5x
        if len(text) < 2 and text.strip():  # Very short (but not empty)
            issues['suspicious_length'] += 1
            logger.debug(f"  Suspiciously short at subtitle {sub['index']}: '{text}'")
    
    # Report summary
    total_issues = sum(issues.values())
    if total_issues == 0:
        logger.info("✓ Quality check passed: No issues found")
    else:
        logger.warning(f"⚠ Quality check found {total_issues} potential issues:")
        for issue_type, count in issues.items():
            if count > 0:
                logger.warning(f"  - {issue_type}: {count}")
    
    return issues


def translate_subtitles_with_gpt(subtitles: List[Dict[str, str]], target_language: str, api_key: str, logger: logging.Logger, translation_format: str = 'json') -> List[Dict[str, str]]:
    """Translate subtitles using gpt-4.1-mini model.

    translation_format: 'json' (default) or 'csv' controls the prompt/parse method.
    """
    logger.info(f"Translating {len(subtitles)} subtitles to {target_language} using gpt-4.1-mini...")
    
    client = OpenAI(api_key=api_key)
    translated_subtitles = []
    
    # Use larger batches to leverage massive 1M token context window
    # 200 subtitles = ~10-20 min of video, well within limits
    batch_size = 200
    total_batches = (len(subtitles) + batch_size - 1) // batch_size
    
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min((batch_idx + 1) * batch_size, len(subtitles))
        batch = subtitles[start_idx:end_idx]
        
        logger.info(f"Processing batch {batch_idx + 1}/{total_batches} ({len(batch)} subtitles)...")
        
        # Build structured prompt based on desired format
        import json
        if translation_format == 'csv':
            # Build CSV header and rows: id,time,text (time unchanged)
            csv_rows = []
            for sub in batch:
                csv_rows.append({'id': sub['index'], 'time': sub['timestamp'], 'text': sub['text']})

            from io import StringIO
            buf = StringIO()
            writer = csv.DictWriter(buf, fieldnames=['id', 'time', 'text'])
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)
            input_csv = buf.getvalue()
            prompt = (
                f"Translate ONLY the 'text' column to {target_language}. Do not change 'id' or 'time'.\n"
                f"Return ONLY valid CSV with the exact same header order: id,time,text.\n\n"
                f"Input CSV:\n{input_csv}"
            )
        else:
            # JSON format (default)
            subtitles_json = []
            for sub in batch:
                subtitles_json.append({
                    "id": sub['index'],
                    "text": sub['text']
                })
            prompt = f"""Translate these subtitles to {target_language}. Return ONLY a JSON array with the same structure.

Input:
{json.dumps(subtitles_json, ensure_ascii=False, indent=2)}

Return format:
[
  {{"id": "1", "text": "translated text"}},
  {{"id": "2", "text": "translated text"}}
]

CRITICAL: Return exactly {len(batch)} items with all IDs from the input."""
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                system_msg = (
                    f"Você é um tradutor profissional. "
                    f"Retorne APENAS um CSV válido com cabeçalho: id,time,text. "
                    f"Traduza todas as legendas para {target_language}. "
                    f"Regras: "
                    f"- Preserve exatamente TODOS os timestamps. "
                    f"- Preserve números, quebras de linha e a ordenação original. "
                    f"- Traduza SOMENTE o texto da legenda. "
                    f"- Não adicione comentários, metadados ou texto fora do CSV."
                    if translation_format == 'csv'
                    else f"Você é um tradutor profissional. "
                        f"Retorne APENAS um array JSON válido. "
                        f"Cada item deve conter: id, time, text. "
                        f"Traduza todas as legendas para {target_language}. "
                        f"Regras: "
                        f"- Preserve exatamente TODOS os timestamps. "
                        f"- Preserve números, quebras de linha e a ordenação original. "
                        f"- Traduza SOMENTE o texto da legenda. "
                        f"- Não adicione comentários, metadados ou texto fora do JSON."
                )
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                
                translated_text = response.choices[0].message.content.strip()
                
                # Debug log first 200 chars if verbose
                logger.debug(f"  Raw response (first 200 chars): {translated_text[:200]}...")

                # Remove markdown code blocks if present
                if translated_text.startswith("```"):
                    parts = translated_text.split("```")
                    # Pick the first inner block if present
                    translated_text = parts[1] if len(parts) > 1 else translated_text
                    # Strip possible language tag
                    if translated_text.startswith("json"):
                        translated_text = translated_text[4:]
                    if translated_text.startswith("csv"):
                        translated_text = translated_text[3:]
                    translated_text = translated_text.strip()

                # Parse response based on format
                translated_dict = {}
                if translation_format == 'csv':
                    # Robust CSV parse
                    from io import StringIO
                    buf = StringIO(translated_text)
                    reader = csv.DictReader(buf)
                    expected_fields = ['id', 'time', 'text']
                    actual_fields = [f.strip().lower() for f in (reader.fieldnames or [])]
                    
                    if actual_fields != expected_fields:
                        error_msg = f"CSV header mismatch. Expected {expected_fields}, got {actual_fields}. First line: {translated_text.split(chr(10))[0]}"
                        logger.debug(f"  {error_msg}")
                        raise ValueError(error_msg)
                    
                    for row in reader:
                        translated_dict[str(row['id'])] = row['text']
                else:
                    # JSON path
                    translated_items = json.loads(translated_text)
                    for item in translated_items:
                        translated_dict[str(item['id'])] = item['text']
                
                # Match translated text back to original subtitles
                batch_success = True
                for sub in batch:
                    if sub['index'] in translated_dict:
                        translated_subtitles.append({
                            'index': sub['index'],
                            'timestamp': sub['timestamp'],
                            'text': translated_dict[sub['index']]
                        })
                    else:
                        batch_success = False
                        if attempt < max_retries - 1:
                            logger.warning(f"Translation missing for subtitle {sub['index']}, retrying batch...")
                            # Remove previously added items from this failed batch
                            translated_subtitles = translated_subtitles[:start_idx]
                            break
                        else:
                            # Final attempt failed, keep original
                            logger.warning(f"Translation missing for subtitle {sub['index']}, keeping original")
                            translated_subtitles.append(sub)
                
                if batch_success:
                    logger.debug(f"  ✓ Batch {batch_idx + 1} translated")
                    break  # Success, exit retry loop
                    
            except (json.JSONDecodeError, ValueError) as e:
                if attempt < max_retries - 1:
                    format_name = "CSV" if translation_format == 'csv' else "JSON"
                    logger.warning(f"{format_name} parse error in batch {batch_idx + 1}, retrying... ({e})")
                    translated_subtitles = translated_subtitles[:start_idx]
                else:
                    logger.error(f"Translation failed for batch {batch_idx + 1} after retries: {e}")
                    # Keep original text if all retries fail
                    translated_subtitles.extend(batch)
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Translation error in batch {batch_idx + 1}, retrying... ({e})")
                    translated_subtitles = translated_subtitles[:start_idx]
                else:
                    logger.error(f"Translation failed for batch {batch_idx + 1} after retries: {e}")
                    # Keep original text if all retries fail
                    translated_subtitles.extend(batch)
    
    logger.info("✓ Translation completed")
    return translated_subtitles


def write_srt_file(subtitles: List[Dict[str, str]], output_path: Path, logger: logging.Logger) -> None:
    """Write subtitles to SRT file."""
    logger.info("Saving translated SRT file...")
    
    srt_content = []
    for sub in subtitles:
        srt_content.append(sub['index'])
        srt_content.append(sub['timestamp'])
        srt_content.append(sub['text'])
        srt_content.append('')  # Empty line
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_content))
        logger.info(f"✓ SRT file saved: {output_path.absolute()}")
    except Exception as e:
        raise RuntimeError(f"Failed to write SRT file: {e}")


def generate_srt(transcriptions: List[Dict], chunk_duration_minutes: int, logger: logging.Logger) -> str:
    """Generate SRT content from transcriptions."""
    logger.info("Generating SRT file...")
    
    srt_lines = []
    subtitle_index = 1
    chunk_duration_seconds = chunk_duration_minutes * 60
    
    for chunk_idx, transcription in enumerate(transcriptions):
        time_offset = chunk_idx * chunk_duration_seconds
        
        segments = transcription.get('segments', [])
        logger.debug(f"  Processing chunk {chunk_idx+1}: {len(segments)} segments")
        
        for segment in segments:
            start_time = segment['start'] + time_offset
            end_time = segment['end'] + time_offset
            text = segment['text'].strip()
            
            if not text:
                continue
            
            srt_lines.append(str(subtitle_index))
            srt_lines.append(f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}")
            srt_lines.append(text)
            srt_lines.append('')  # Empty line between subtitles
            
            subtitle_index += 1
    
    logger.info(f"✓ Generated {subtitle_index - 1} subtitles")
    return '\n'.join(srt_lines)


def cleanup_temp_files(logger: logging.Logger) -> None:
    """Clean up temporary chunk files."""
    if TEMP_DIR.exists():
        logger.debug("Cleaning up temporary files...")
        shutil.rmtree(TEMP_DIR)
        logger.debug("✓ Temporary files cleaned")


def main():
    """Main application entry point."""
    args = parse_arguments()
    logger = setup_logging(args.verbose)
    
    try:
        # Load environment variables
        load_dotenv()
        
        # Get API key
        api_key = args.api_key or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY in .env file "
                "or provide it via --api-key parameter"
            )
        
        # Handle only-translation mode (no audio processing)
        if args.only_translation:
            if not args.translate:
                raise ValueError("--translate parameter is required when using --only-translation")
            
            srt_path = Path(args.only_translation)
            if not srt_path.exists():
                raise FileNotFoundError(f"SRT file not found: {args.only_translation}")
            
            # Parse SRT file
            subtitles = parse_srt_file(srt_path, logger)
            
            # Translate subtitles
            translated_subtitles = translate_subtitles_with_gpt(
                subtitles,
                args.translate,
                api_key,
                logger,
                translation_format=args.translation_format
            )
            
            # Quality check
            quality_check_translations(translated_subtitles, args.translate, logger)
            
            # Determine output path
            if args.output:
                output_path = Path(args.output)
            else:
                # Add language suffix to filename
                output_path = srt_path.with_stem(f"{srt_path.stem}_{args.translate}")
            
            # Write translated SRT
            write_srt_file(translated_subtitles, output_path, logger)
            
            logger.info(f"✓ Completed! Translated SRT file: {output_path.absolute()}")
            return
        
        # Validate input file (for audio processing)
        if not args.input:
            raise ValueError("--input parameter is required (or use --only-translation for SRT translation)")
        
        input_path = validate_audio_file(args.input, logger)
        
        # Determine output path
        output_path = Path(args.output) if args.output else input_path.with_suffix('.srt')
        logger.info(f"Output will be saved to: {output_path}")
        
        # Generate file hash for caching
        file_hash = get_file_hash(input_path)
        logger.debug(f"File hash: {file_hash}")
        
        # Get audio duration
        audio_duration = get_audio_duration(input_path, logger)
        
        # Split audio if needed
        chunks = split_audio_into_chunks(audio_duration, input_path, args.chunk_duration, logger)
        
        try:
            # Transcribe or translate
            transcriptions = transcribe_audio(
                chunks,
                api_key,
                args.language,
                args.translate,
                file_hash,
                args.clear_cache,
                logger
            )
            
            # Generate SRT
            srt_content = generate_srt(transcriptions, args.chunk_duration, logger)
            
            # Save SRT file
            logger.info("Saving SRT file...")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            logger.info(f"✓ Completed! SRT file saved: {output_path.absolute()}")
            
        finally:
            # Always cleanup temporary files
            cleanup_temp_files(logger)
    
    except KeyboardInterrupt:
        logger.error("\n✗ Operation cancelled by user")
        cleanup_temp_files(logger)
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        cleanup_temp_files(logger)
        sys.exit(1)


if __name__ == '__main__':
    main()
