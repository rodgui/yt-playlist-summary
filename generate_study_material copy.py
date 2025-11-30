#!/usr/bin/env python3
"""
Study Material Generator

Consolidates SRT subtitles from a playlist and generates unified study content
using GPT-4.1-mini. Processes existing subtitle files without re-downloading or
re-transcribing videos.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import hashlib

from openai import OpenAI

logger = logging.getLogger('study_material_generator')


def parse_srt_file(srt_path: str) -> List[Dict[str, str]]:
    """
    Parse SRT file and extract text segments with timestamps.
    Returns list of dicts with 'index', 'timestamp', 'text'.
    """
    segments = []
    
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by double newline (segment separator)
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            try:
                index = lines[0].strip()
                timestamp = lines[1].strip()
                text = ' '.join(lines[2:]).strip()
                
                if text:
                    segments.append({
                        'index': index,
                        'timestamp': timestamp,
                        'text': text
                    })
            except Exception as e:
                logger.debug(f"Skipping malformed block: {e}")
                continue
        
        logger.debug(f"Parsed {len(segments)} segments from {Path(srt_path).name}")
        return segments
        
    except Exception as e:
        logger.error(f"Failed to parse {srt_path}: {e}")
        return []


def extract_video_metadata_from_filename(filename: str) -> Dict[str, str]:
    """
    Extract metadata from standardized filename: '<idx>. <title>.<lang>.srt'
    Returns dict with 'index', 'title', 'language'.
    """
    name = Path(filename).stem
    
    # Pattern: "1. Title.pt-BR" or "1. Title.whisper"
    match = re.match(r'^(\d+)\.\s*(.+?)(?:\.([a-z]{2}(?:[-_][A-Z]{2})?|whisper))?$', name)
    
    if match:
        idx, title, lang = match.groups()
        return {
            'index': int(idx),
            'title': title.strip(),
            'language': lang or 'unknown'
        }
    
    # Fallback: treat entire name as title
    return {
        'index': 0,
        'title': name,
        'language': 'unknown'
    }


def consolidate_playlist_subtitles(
    subtitle_dir: str,
    output_format: str = 'markdown'
) -> str:
    """
    Consolidate all SRT files in directory into structured text.
    Returns consolidated content string (Markdown or JSON).
    """
    if not os.path.isdir(subtitle_dir):
        raise ValueError(f"Subtitle directory not found: {subtitle_dir}")
    
    # Collect all SRT files
    srt_files = sorted([
        f for f in os.listdir(subtitle_dir)
        if f.endswith('.srt')
    ])
    
    if not srt_files:
        raise ValueError(f"No SRT files found in {subtitle_dir}")
    
    logger.info(f"📚 Consolidando {len(srt_files)} arquivo(s) de legenda...")
    
    # Group by video (same index prefix)
    videos_content = []
    
    for srt_file in srt_files:
        srt_path = os.path.join(subtitle_dir, srt_file)
        metadata = extract_video_metadata_from_filename(srt_file)
        segments = parse_srt_file(srt_path)
        
        if not segments:
            logger.warning(f"  ⚠️  Arquivo vazio ou inválido: {srt_file}")
            continue
        
        # Concatenate all segment texts
        full_text = ' '.join(seg['text'] for seg in segments)
        
        videos_content.append({
            'file': srt_file,
            'index': metadata['index'],
            'title': metadata['title'],
            'language': metadata['language'],
            'segments': segments,
            'full_text': full_text,
            'word_count': len(full_text.split())
        })
        
        logger.info(f"  ✅ {metadata['index']}. {metadata['title']} ({len(segments)} segmentos)")
    
    # Sort by index
    videos_content.sort(key=lambda x: x['index'])
    
    # Generate output based on format
    if output_format == 'json':
        return json.dumps(videos_content, ensure_ascii=False, indent=2)
    
    # Markdown format (default)
    lines = [
        "# Material de Estudo Consolidado",
        f"\n**Total de vídeos:** {len(videos_content)}",
        f"**Gerado em:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n---\n"
    ]
    
    for video in videos_content:
        lines.append(f"\n## {video['index']}. {video['title']}")
        lines.append(f"\n**Idioma:** {video['language']} | **Palavras:** {video['word_count']}")
        lines.append(f"\n### Conteúdo\n")
        lines.append(video['full_text'])
        lines.append("\n---\n")
    
    return '\n'.join(lines)


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~0.75 tokens per word for Portuguese/English."""
    return int(len(text.split()) * 0.75)


def generate_study_content_with_gpt(
    consolidated_text: str,
    api_key: str,
    language: str = 'pt',
    model: str = 'gpt-4o-mini',
    temperature: float = 0.3,
    max_tokens: int = 100000
) -> str:
    """
    Send consolidated subtitle text to GPT and generate structured study material.
    Returns formatted Markdown content.
    """
    client = OpenAI(api_key=api_key)
    
    # Build prompt based on target language
    prompts = {
        'pt': """Você é um especialista educacional. Analise o conteúdo transcrito de uma playlist de vídeos e crie um material de estudo COMPLETO, DETALHADO e ABRANGENTE.

**IMPORTANTE:** Este material será usado como ÚNICA FONTE DE ESTUDO. O aluno NÃO assistirá aos vídeos. Portanto, você deve:
- Extrair e explicar TODOS os conceitos apresentados em profundidade
- Manter TODOS os exemplos, casos práticos, demonstrações e códigos mencionados
- Preservar detalhes técnicos, nuances e contexto
- Expandir explicações quando necessário para clareza
- Criar um documento que substitua completamente os vídeos

O material deve incluir:

1. **Resumo Executivo** (3-5 parágrafos): Visão geral completa dos tópicos, objetivos e estrutura da playlist

2. **Conceitos-Chave**: Lista detalhada de todos os conceitos principais com:
   - Definições completas e precisas
   - Contexto de uso
   - Relações entre conceitos
   - Exemplos ilustrativos

3. **Conteúdo por Vídeo** (MÍNIMO 200-400 palavras por vídeo):
   Para cada vídeo, desenvolva:
   - **Resumo detalhado** do conteúdo (4-6 parágrafos)
   - **Conceitos apresentados** com explicações completas
   - **Pontos principais** em bullet points expandidos
   - **Exemplos práticos** com descrição completa (código, casos de uso, demonstrações)
   - **Detalhes técnicos** e especificações mencionadas
   - **Dicas e boas práticas** compartilhadas
   - **Armadilhas comuns** e como evitá-las
   - **Relação com vídeos anteriores/posteriores** no contexto da progressão do curso

4. **Exemplos e Casos Práticos Consolidados**:
   - Todos os exemplos de código com explicação linha por linha
   - Casos de uso reais mencionados
   - Demonstrações práticas descritas em detalhe
   - Screenshots ou diagramas descritos verbalmente

5. **Exercícios e Pontos de Ação**:
   - Checklist detalhada de tarefas sugeridas
   - Exercícios práticos mencionados com instruções completas
   - Projetos sugeridos para aplicação dos conceitos

6. **Glossário Técnico**:
   - Todos os termos técnicos com definições completas
   - Acrônimos e suas expansões
   - Jargão específico do domínio

7. **Referências e Recursos**:
   - Links, ferramentas e bibliotecas mencionadas
   - Documentação oficial citada
   - Recursos adicionais recomendados
   - Timestamps aproximados para referência cruzada

8. **Apêndices** (se aplicável):
   - Comandos e configurações importantes
   - Snippets de código reutilizáveis
   - Tabelas comparativas
   - Fluxogramas descritos verbalmente

**Formato:** Markdown rico, com títulos hierárquicos, subtítulos, listas, tabelas, blocos de código, citações e ênfases.

**Tom:** Educacional, detalhado, preciso e engajador. Priorize COMPLETUDE sobre brevidade.

**Meta de tamanho:** 30.000 a 50.000 palavras para playlists com 50-150 vídeos. Média de 200-400 palavras por vídeo.

**Conteúdo das legendas:**

""",
        'en': """You are an educational expert. Analyze the transcribed content from a video playlist and create COMPLETE, DETAILED, and COMPREHENSIVE study material.

**CRITICAL:** This material will be used as the SOLE STUDY SOURCE. The student will NOT watch the videos. Therefore, you must:
- Extract and explain ALL concepts presented in depth
- Maintain ALL examples, practical cases, demonstrations, and code mentioned
- Preserve technical details, nuances, and context
- Expand explanations when necessary for clarity
- Create a document that completely replaces the videos

The material should include:

1. **Executive Summary** (3-5 paragraphs): Complete overview of topics, objectives, and playlist structure

2. **Key Concepts**: Detailed list of all main concepts with:
   - Complete and precise definitions
   - Usage context
   - Relationships between concepts
   - Illustrative examples

3. **Content by Video** (MINIMUM 200-400 words per video):
   For each video, develop:
   - **Detailed summary** of content (4-6 paragraphs)
   - **Concepts presented** with complete explanations
   - **Main points** in expanded bullet points
   - **Practical examples** with full description (code, use cases, demonstrations)
   - **Technical details** and specifications mentioned
   - **Tips and best practices** shared
   - **Common pitfalls** and how to avoid them
   - **Relationship with previous/next videos** in the course progression context

4. **Consolidated Examples and Practical Cases**:
   - All code examples with line-by-line explanation
   - Real-world use cases mentioned
   - Practical demonstrations described in detail
   - Screenshots or diagrams described verbally

5. **Exercises and Action Points**:
   - Detailed checklist of suggested tasks
   - Practical exercises mentioned with complete instructions
   - Suggested projects for concept application

6. **Technical Glossary**:
   - All technical terms with complete definitions
   - Acronyms and their expansions
   - Domain-specific jargon

7. **References and Resources**:
   - Links, tools, and libraries mentioned
   - Official documentation cited
   - Additional recommended resources
   - Approximate timestamps for cross-reference

8. **Appendices** (if applicable):
   - Important commands and configurations
   - Reusable code snippets
   - Comparison tables
   - Flowcharts described verbally

**Format:** Rich Markdown with hierarchical headings, subheadings, lists, tables, code blocks, quotes, and emphasis.

**Tone:** Educational, detailed, precise, and engaging. Prioritize COMPLETENESS over brevity.

**Size target:** 30,000 to 50,000 words for playlists with 50-150 videos. Average 200-400 words per video.

**Subtitle content:**

"""
    }
    
    prompt = prompts.get(language, prompts['pt']) + consolidated_text
    
    input_tokens = estimate_tokens(prompt)
    logger.info(f"📊 Tokens estimados (entrada): ~{input_tokens:,}")
    
    if input_tokens > 120000:  # Context limit safety
        logger.warning(f"⚠️  Texto muito longo ({input_tokens:,} tokens). Considere processar em lotes.")
    
    logger.info(f"🤖 Enviando para {model} (temperature={temperature})...")
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert educational content creator."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        content = response.choices[0].message.content
        
        # Log usage
        usage = response.usage
        logger.info(f"✅ Resposta recebida")
        logger.info(f"   📥 Tokens entrada: {usage.prompt_tokens:,}")
        logger.info(f"   📤 Tokens saída: {usage.completion_tokens:,}")
        logger.info(f"   💰 Total: {usage.total_tokens:,}")
        
        return content
        
    except Exception as e:
        logger.error(f"❌ Falha na geração com GPT: {e}")
        raise


def generate_playlist_study_content(
    subtitle_dir: str,
    output_path: str,
    api_key: str,
    study_language: str = 'pt',
    consolidation_format: str = 'markdown',
    skip_gpt: bool = False,
    interactive: bool = False
) -> str:
    """
    Main function: consolidate SRT files and generate study material.
    Returns path to generated file.
    """
    logger.info("=" * 60)
    logger.info("📚 GERAÇÃO DE MATERIAL DE ESTUDO")
    logger.info("=" * 60)
    
    # Step 1: Consolidate subtitles
    logger.info("🔄 Etapa 1: Consolidando legendas...")
    consolidated = consolidate_playlist_subtitles(subtitle_dir, consolidation_format)
    
    # Estimate costs and duration
    total_tokens = estimate_tokens(consolidated)
    estimated_input_cost = (total_tokens / 1_000_000) * 0.15  # $0.15 per 1M tokens (input)
    estimated_output_cost = (100_000 / 1_000_000) * 0.60  # $0.60 per 1M tokens (output, max 100k)
    estimated_total_cost = estimated_input_cost + estimated_output_cost
    estimated_duration_seconds = (total_tokens / 1000) * 2  # ~2 seconds per 1k tokens
    estimated_duration_minutes = int(estimated_duration_seconds / 60)
    estimated_duration_seconds_remainder = int(estimated_duration_seconds % 60)
    
    # Save consolidated version (optional intermediate step)
    consolidated_path = output_path.replace('.md', '_consolidated.md')
    with open(consolidated_path, 'w', encoding='utf-8') as f:
        f.write(consolidated)
    logger.info(f"💾 Consolidado salvo: {Path(consolidated_path).name}")
    
    if skip_gpt:
        logger.info("⏭️  Pulando geração via GPT (--skip-gpt)")
        return consolidated_path
    
    # Display summary and ask for confirmation
    logger.info("=" * 60)
    logger.info("📊 RESUMO DA OPERAÇÃO")
    logger.info("=" * 60)
    logger.info(f"📝 Caracteres: {len(consolidated):,}")
    logger.info(f"🔢 Tokens estimados (entrada): ~{total_tokens:,}")
    logger.info(f"💰 Custo estimado:")
    logger.info(f"   • Entrada: ${estimated_input_cost:.4f} USD")
    logger.info(f"   • Saída: ${estimated_output_cost:.4f} USD")
    logger.info(f"   • Total: ${estimated_total_cost:.4f} USD")
    
    if estimated_duration_minutes > 0:
        logger.info(f"⏱️  Duração estimada: ~{estimated_duration_minutes}m {estimated_duration_seconds_remainder}s")
    else:
        logger.info(f"⏱️  Duração estimada: ~{estimated_duration_seconds_remainder}s")
    
    logger.info(f"🤖 Modelo: gpt-4o-mini")
    logger.info("=" * 60)
    
    # Always ask for confirmation before sending to GPT
    response = input("▶️  Prosseguir com a Etapa 2 (enviar para GPT)? (s/n): ").strip().lower()
    if response not in ['s', 'sim', 'y', 'yes']:
        logger.info("🛑 Geração cancelada pelo usuário")
        logger.info(f"ℹ️  O arquivo consolidado foi salvo em: {consolidated_path}")
        return consolidated_path
    
    # Step 2: Generate study material with GPT
    logger.info("=" * 60)
    logger.info("🤖 Etapa 2: Gerando material de estudo via GPT...")
    logger.info("=" * 60)
    
    study_content = generate_study_content_with_gpt(
        consolidated,
        api_key,
        language=study_language
    )
    
    # Save final study material
    with open(output_path, 'w', encoding='utf-8') as f:
        # Add header with metadata
        header = f"""# Material de Estudo - Playlist
**Gerado em:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Fonte:** {subtitle_dir}

---

"""
        f.write(header + study_content)
    
    logger.info("=" * 60)
    logger.info(f"✅ Material de estudo salvo: {Path(output_path).name}")
    logger.info(f"📄 Tamanho: {len(study_content):,} caracteres")
    logger.info("=" * 60)
    
    return output_path


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate study material from playlist subtitles'
    )
    parser.add_argument(
        '-s', '--subtitle-dir',
        type=str,
        required=True,
        help='Directory containing SRT subtitle files'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output file path (default: study_material_TIMESTAMP.md)'
    )
    parser.add_argument(
        '-k', '--api-key',
        type=str,
        default=os.environ.get('OPENAI_API_KEY'),
        help='OpenAI API key'
    )
    parser.add_argument(
        '-l', '--language',
        type=str,
        default='pt',
        choices=['pt', 'en'],
        help='Study material language (default: pt)'
    )
    parser.add_argument(
        '--skip-gpt',
        action='store_true',
        help='Only consolidate subtitles, skip GPT generation'
    )
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Ask confirmation for large playlists'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    if not args.skip_gpt and not args.api_key:
        logger.error("❌ OpenAI API key required (use --api-key or OPENAI_API_KEY)")
        exit(1)
    
    # Generate output filename if not provided
    if not args.output:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output = f"study_material_{timestamp}.md"
    
    try:
        result = generate_playlist_study_content(
            subtitle_dir=args.subtitle_dir,
            output_path=args.output,
            api_key=args.api_key or '',
            study_language=args.language,
            skip_gpt=args.skip_gpt,
            interactive=args.interactive
        )
        
        if result:
            logger.info("✨ Concluído!")
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        exit(1)