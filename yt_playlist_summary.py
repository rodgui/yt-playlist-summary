#!/usr/bin/env python3
"""
YouTube Playlist Summary Tool

A solution that receives a YouTube playlist URL, downloads videos,
extracts audio, converts to mp3, transcribes using OpenAI Whisper API,
and generates SRT subtitle files.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import yt_dlp
from openai import OpenAI
from pydub import AudioSegment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging level based on verbosity."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")


def download_playlist(
    playlist_url: str,
    output_dir: str,
    audio_only: bool = False
) -> list[str]:
    """
    Download videos from a YouTube playlist.
    
    Args:
        playlist_url: URL of the YouTube playlist
        output_dir: Directory to save downloaded files
        audio_only: If True, download only audio
        
    Returns:
        List of paths to downloaded files
    """
    downloaded_files = []
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Configure yt-dlp options
    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(playlist_index)s_%(title)s.%(ext)s'),
        'ignoreerrors': True,
        'no_warnings': False,
        'extract_flat': False,
        'progress_hooks': [lambda d: logger.debug(f"Download progress: {d.get('status', 'unknown')}")],
    }
    
    if audio_only:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
        logger.info("Downloading audio only")
    else:
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        })
        logger.info("Downloading video and audio")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Starting download from playlist: {playlist_url}")
            
            # Extract playlist info first
            info = ydl.extract_info(playlist_url, download=False)
            
            if info is None:
                logger.error("Failed to extract playlist information")
                return downloaded_files
            
            # Check if it's a playlist or single video
            if 'entries' in info:
                total_videos = len([e for e in info['entries'] if e is not None])
                logger.info(f"Found {total_videos} videos in playlist")
            else:
                logger.info("Processing single video")
            
            # Download the videos
            ydl.download([playlist_url])
            
            # Get list of downloaded files
            for file in os.listdir(output_dir):
                file_path = os.path.join(output_dir, file)
                if os.path.isfile(file_path):
                    downloaded_files.append(file_path)
                    logger.debug(f"Downloaded: {file_path}")
            
            logger.info(f"Downloaded {len(downloaded_files)} files")
            
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during download: {e}")
        raise
    
    return downloaded_files


def extract_audio(video_path: str, output_dir: str) -> str:
    """
    Extract audio from a video file.
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save the extracted audio
        
    Returns:
        Path to the extracted audio file
    """
    os.makedirs(output_dir, exist_ok=True)
    
    video_name = Path(video_path).stem
    audio_path = os.path.join(output_dir, f"{video_name}.mp3")
    
    try:
        logger.info(f"Extracting audio from: {video_path}")
        audio = AudioSegment.from_file(video_path)
        audio.export(audio_path, format="mp3")
        logger.info(f"Audio extracted to: {audio_path}")
        return audio_path
    except Exception as e:
        logger.error(f"Failed to extract audio from {video_path}: {e}")
        raise


def convert_audio_to_mono_64kbps(
    audio_path: str,
    output_dir: str,
    keep_original: bool = False
) -> str:
    """
    Convert audio file to mp3 64kbps mono format.
    
    Args:
        audio_path: Path to the input audio file
        output_dir: Directory to save the converted audio
        keep_original: If True, keep original format without conversion
        
    Returns:
        Path to the converted (or original) audio file
    """
    if keep_original:
        logger.info(f"Keeping original audio format: {audio_path}")
        return audio_path
    
    os.makedirs(output_dir, exist_ok=True)
    
    audio_name = Path(audio_path).stem
    converted_path = os.path.join(output_dir, f"{audio_name}_64kbps_mono.mp3")
    
    try:
        logger.info(f"Converting audio to 64kbps mono: {audio_path}")
        audio = AudioSegment.from_file(audio_path)
        
        # Convert to mono
        audio = audio.set_channels(1)
        
        # Export with 64kbps bitrate
        audio.export(
            converted_path,
            format="mp3",
            bitrate="64k"
        )
        
        logger.info(f"Audio converted to: {converted_path}")
        return converted_path
    except Exception as e:
        logger.error(f"Failed to convert audio {audio_path}: {e}")
        raise


def transcribe_audio(
    audio_path: str,
    api_key: str,
    model: str = "whisper-1"
) -> dict:
    """
    Transcribe audio using OpenAI Whisper API.
    
    Args:
        audio_path: Path to the audio file
        api_key: OpenAI API key
        model: Whisper model to use
        
    Returns:
        Transcription response from OpenAI API
    """
    try:
        logger.info(f"Transcribing audio: {audio_path}")
        logger.debug(f"Using model: {model}")
        
        client = OpenAI(api_key=api_key)
        
        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        
        logger.info("Transcription completed successfully")
        return response
    except Exception as e:
        logger.error(f"Failed to transcribe audio {audio_path}: {e}")
        raise


def format_timestamp(seconds: float) -> str:
    """
    Format seconds to SRT timestamp format (HH:MM:SS,mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def generate_srt(transcription: dict, output_path: str) -> str:
    """
    Generate SRT subtitle file from transcription.
    
    Args:
        transcription: Transcription response from OpenAI
        output_path: Path to save the SRT file
        
    Returns:
        Path to the generated SRT file
    """
    try:
        logger.info(f"Generating SRT file: {output_path}")
        
        srt_content = []
        
        # Extract segments from transcription
        segments = getattr(transcription, 'segments', None) or []
        
        for i, segment in enumerate(segments, 1):
            start_time = segment.get('start', 0) if isinstance(segment, dict) else getattr(segment, 'start', 0)
            end_time = segment.get('end', 0) if isinstance(segment, dict) else getattr(segment, 'end', 0)
            text = segment.get('text', '').strip() if isinstance(segment, dict) else getattr(segment, 'text', '').strip()
            
            start_formatted = format_timestamp(start_time)
            end_formatted = format_timestamp(end_time)
            
            srt_content.append(f"{i}")
            srt_content.append(f"{start_formatted} --> {end_formatted}")
            srt_content.append(text)
            srt_content.append("")
        
        # If no segments, use full text as single subtitle
        if not segments:
            text = getattr(transcription, 'text', '') or ''
            if text:
                srt_content.append("1")
                srt_content.append("00:00:00,000 --> 00:00:10,000")
                srt_content.append(text.strip())
                srt_content.append("")
        
        # Write SRT file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_content))
        
        logger.info(f"SRT file generated: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to generate SRT file: {e}")
        raise


def process_playlist(
    playlist_url: str,
    output_dir: str,
    api_key: str,
    audio_only: bool = False,
    keep_original_audio: bool = False,
    model: str = "whisper-1",
    skip_transcription: bool = False
) -> list[dict]:
    """
    Process a YouTube playlist: download, extract audio, convert, transcribe, and generate SRT.
    
    Args:
        playlist_url: URL of the YouTube playlist
        output_dir: Base output directory
        api_key: OpenAI API key
        audio_only: Download only audio
        keep_original_audio: Keep original audio format
        model: Whisper model to use
        skip_transcription: Skip transcription step
        
    Returns:
        List of results for each processed video
    """
    results = []
    
    # Create directory structure
    downloads_dir = os.path.join(output_dir, "downloads")
    audio_dir = os.path.join(output_dir, "audio")
    converted_dir = os.path.join(output_dir, "converted")
    srt_dir = os.path.join(output_dir, "subtitles")
    
    for directory in [downloads_dir, audio_dir, converted_dir, srt_dir]:
        os.makedirs(directory, exist_ok=True)
    
    try:
        # Step 1: Download playlist
        logger.info("=" * 50)
        logger.info("Step 1: Downloading playlist")
        logger.info("=" * 50)
        
        downloaded_files = download_playlist(
            playlist_url,
            downloads_dir,
            audio_only=audio_only
        )
        
        if not downloaded_files:
            logger.warning("No files were downloaded")
            return results
        
        # Process each downloaded file
        for file_path in downloaded_files:
            result = {
                'original_file': file_path,
                'audio_file': None,
                'converted_file': None,
                'srt_file': None,
                'status': 'pending'
            }
            
            try:
                file_name = Path(file_path).stem
                
                # Step 2: Extract audio (if not audio_only)
                if audio_only:
                    audio_path = file_path
                    result['audio_file'] = audio_path
                else:
                    logger.info("=" * 50)
                    logger.info(f"Step 2: Extracting audio from {file_name}")
                    logger.info("=" * 50)
                    
                    audio_path = extract_audio(file_path, audio_dir)
                    result['audio_file'] = audio_path
                
                # Step 3: Convert audio
                logger.info("=" * 50)
                logger.info(f"Step 3: Converting audio for {file_name}")
                logger.info("=" * 50)
                
                converted_path = convert_audio_to_mono_64kbps(
                    audio_path,
                    converted_dir,
                    keep_original=keep_original_audio
                )
                result['converted_file'] = converted_path
                
                # Step 4: Transcribe audio
                if not skip_transcription:
                    logger.info("=" * 50)
                    logger.info(f"Step 4: Transcribing audio for {file_name}")
                    logger.info("=" * 50)
                    
                    transcription = transcribe_audio(
                        converted_path,
                        api_key,
                        model=model
                    )
                    
                    # Step 5: Generate SRT
                    logger.info("=" * 50)
                    logger.info(f"Step 5: Generating SRT for {file_name}")
                    logger.info("=" * 50)
                    
                    srt_path = os.path.join(srt_dir, f"{file_name}.srt")
                    generate_srt(transcription, srt_path)
                    result['srt_file'] = srt_path
                
                result['status'] = 'success'
                logger.info(f"Successfully processed: {file_name}")
                
            except Exception as e:
                result['status'] = 'error'
                result['error'] = str(e)
                logger.error(f"Failed to process {file_path}: {e}")
            
            results.append(result)
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to process playlist: {e}")
        raise


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='YouTube Playlist Summary Tool - Download, transcribe, and generate subtitles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download and transcribe a playlist
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..."

  # Download audio only
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --audio-only

  # Keep original audio format (no conversion)
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --keep-original

  # Specify Whisper model
  %(prog)s --url "https://youtube.com/playlist?list=..." --api-key "sk-..." --model whisper-1

  # Skip transcription (download and convert only)
  %(prog)s --url "https://youtube.com/playlist?list=..." --skip-transcription
        """
    )
    
    parser.add_argument(
        '-u', '--url',
        type=str,
        required=True,
        help='YouTube playlist URL or single video URL'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='./output',
        help='Output directory (default: ./output)'
    )
    
    parser.add_argument(
        '-k', '--api-key',
        type=str,
        default=os.environ.get('OPENAI_API_KEY'),
        help='OpenAI API key (can also be set via OPENAI_API_KEY environment variable)'
    )
    
    parser.add_argument(
        '-m', '--model',
        type=str,
        default='whisper-1',
        help='Whisper model to use (default: whisper-1)'
    )
    
    parser.add_argument(
        '-a', '--audio-only',
        action='store_true',
        help='Download only audio (no video)'
    )
    
    parser.add_argument(
        '--keep-original',
        action='store_true',
        help='Keep original audio format (do not convert to 64kbps mono)'
    )
    
    parser.add_argument(
        '--skip-transcription',
        action='store_true',
        help='Skip transcription step (download and convert only)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_arguments()
    
    # Setup logging
    setup_logging(args.verbose)
    
    logger.info("=" * 60)
    logger.info("YouTube Playlist Summary Tool")
    logger.info("=" * 60)
    
    # Validate API key
    if not args.skip_transcription and not args.api_key:
        logger.error("OpenAI API key is required for transcription. "
                    "Use --api-key or set OPENAI_API_KEY environment variable. "
                    "Or use --skip-transcription to skip transcription.")
        return 1
    
    # Log configuration
    logger.info(f"Playlist URL: {args.url}")
    logger.info(f"Output directory: {args.output}")
    logger.info(f"Audio only: {args.audio_only}")
    logger.info(f"Keep original audio: {args.keep_original}")
    logger.info(f"Whisper model: {args.model}")
    logger.info(f"Skip transcription: {args.skip_transcription}")
    
    try:
        results = process_playlist(
            playlist_url=args.url,
            output_dir=args.output,
            api_key=args.api_key or '',
            audio_only=args.audio_only,
            keep_original_audio=args.keep_original,
            model=args.model,
            skip_transcription=args.skip_transcription
        )
        
        # Print summary
        logger.info("=" * 60)
        logger.info("Processing Summary")
        logger.info("=" * 60)
        
        success_count = sum(1 for r in results if r['status'] == 'success')
        error_count = sum(1 for r in results if r['status'] == 'error')
        
        logger.info(f"Total files processed: {len(results)}")
        logger.info(f"Successful: {success_count}")
        logger.info(f"Errors: {error_count}")
        
        if error_count > 0:
            logger.warning("Some files failed to process:")
            for r in results:
                if r['status'] == 'error':
                    logger.warning(f"  - {r['original_file']}: {r.get('error', 'Unknown error')}")
        
        return 0 if error_count == 0 else 1
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
