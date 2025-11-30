#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Study Material Generator (GPT-5)

Variante do gerador de material de estudo usando o modelo gpt-5-mini
com a nova API `client.responses.create` da OpenAI.

Reaproveita a lógica de consolidação de legendas de `generate_study_material.py`
mas usa a Responses API para gerar o conteúdo final.
"""

import os
import logging
from pathlib import Path
from datetime import datetime

from typing import Optional

from openai import OpenAI

# Reutiliza funções utilitárias do módulo original
from generate_study_material import (
    consolidate_playlist_subtitles,
    estimate_tokens,
)

logger = logging.getLogger("study_material_generator_gpt5")


def generate_study_content_with_gpt5(
    consolidated_text: str,
    api_key: str,
    language: str = "pt",
    model: str = "gpt-5-mini",
    temperature: float = 0.3,
    max_output_tokens: int = 120000,
) -> str:
    """Gera material de estudo estruturado usando GPT-5 (Responses API)."""
    client = OpenAI(api_key=api_key)

    prompts = {
        "pt": """Você é um especialista educacional. Analise o conteúdo transcrito de uma playlist de vídeos e crie um material de estudo COMPLETO, DETALHADO e ABRANGENTE.

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
        "en": """You are an educational expert. Analyze the transcribed content from a video playlist and create COMPLETE, DETAILED, and COMPREHENSIVE study material.

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

""",
    }

    prompt = prompts.get(language, prompts["pt"]) + consolidated_text

    input_tokens = estimate_tokens(prompt)
    logger.info(f"📊 Tokens estimados (entrada): ~{input_tokens:,}")

    if input_tokens > 120000:
        logger.warning(
            f"⚠️  Texto muito longo ({input_tokens:,} tokens). Considere processar em lotes."
        )

    logger.info(f"🤖 Enviando para {model} (temperature={temperature}) via Responses API...")

    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": "You are an expert educational content creator."},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        # Dependendo da versão da SDK, `output_text` pode estar disponível
        content: Optional[str] = None

        if hasattr(response, "output_text"):
            content = response.output_text
        else:
            # Fallback genérico para responses.output[*].content[*].text
            try:
                parts = []
                for out in getattr(response, "output", []) or []:
                    for c in getattr(out, "content", []) or []:
                        text_obj = getattr(c, "text", None)
                        if text_obj is None:
                            continue
                        value = getattr(text_obj, "value", None) or getattr(text_obj, "text", None)
                        if isinstance(value, str):
                            parts.append(value)
                content = "".join(parts) if parts else None
            except Exception:
                content = None

        if not content:
            raise RuntimeError("Não foi possível extrair o texto da resposta de GPT-5.")

        # Log de uso de tokens, se disponível
        usage = getattr(response, "usage", None)
        if usage is not None:
            in_tokens = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
            out_tokens = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)

            logger.info("✅ Resposta recebida")
            if in_tokens is not None:
                logger.info(f"   📥 Tokens entrada: {in_tokens:,}")
            if out_tokens is not None:
                logger.info(f"   📤 Tokens saída: {out_tokens:,}")
            if total_tokens is not None:
                logger.info(f"   💰 Total: {total_tokens:,}")
        else:
            logger.info("✅ Resposta recebida (sem métricas de uso disponíveis)")

        return content

    except Exception as e:
        logger.error(f"❌ Falha na geração com GPT-5: {e}")
        raise


def generate_playlist_study_content_gpt5(
    subtitle_dir: str,
    output_path: str,
    api_key: str,
    study_language: str = "pt",
    consolidation_format: str = "markdown",
    skip_gpt: bool = False,
    interactive: bool = False,
) -> str:
    """Fluxo principal usando GPT-5: consolida legendas e gera material de estudo."""
    logger.info("=" * 60)
    logger.info("📚 GERAÇÃO DE MATERIAL DE ESTUDO (GPT-5)")
    logger.info("=" * 60)

    logger.info("🔄 Etapa 1: Consolidando legendas...")
    consolidated = consolidate_playlist_subtitles(subtitle_dir, consolidation_format)

    # Estimativa de custos e duração (mantém lógica aproximada do script original)
    total_tokens = estimate_tokens(consolidated)
    estimated_input_cost = (total_tokens / 1_000_000) * 0.15  # exemplo: $0.15 / 1M tokens (entrada)
    estimated_output_cost = (100_000 / 1_000_000) * 0.60  # exemplo: $0.60 / 1M tokens (saída, 100k)
    estimated_total_cost = estimated_input_cost + estimated_output_cost
    estimated_duration_seconds = (total_tokens / 1000) * 2  # ~2s por 1k tokens
    estimated_duration_minutes = int(estimated_duration_seconds / 60)
    estimated_duration_seconds_remainder = int(estimated_duration_seconds % 60)

    # Salva versão consolidada
    consolidated_path = output_path.replace(".md", "_consolidated.md")
    with open(consolidated_path, "w", encoding="utf-8") as f:
        f.write(consolidated)
    logger.info(f"💾 Consolidado salvo: {Path(consolidated_path).name}")

    if skip_gpt:
        logger.info("⏭️  Pulando geração via GPT-5 (--skip-gpt)")
        return consolidated_path

    # Resumo e confirmação
    logger.info("=" * 60)
    logger.info("📊 RESUMO DA OPERAÇÃO (GPT-5)")
    logger.info("=" * 60)
    logger.info(f"📝 Caracteres: {len(consolidated):,}")
    logger.info(f"🔢 Tokens estimados (entrada): ~{total_tokens:,}")
    logger.info("💰 Custo estimado (aprox.):")
    logger.info(f"   • Entrada: ${estimated_input_cost:.4f} USD")
    logger.info(f"   • Saída: ${estimated_output_cost:.4f} USD")
    logger.info(f"   • Total: ${estimated_total_cost:.4f} USD")

    if estimated_duration_minutes > 0:
        logger.info(
            f"⏱️  Duração estimada: ~{estimated_duration_minutes}m {estimated_duration_seconds_remainder}s"
        )
    else:
        logger.info(f"⏱️  Duração estimada: ~{estimated_duration_seconds_remainder}s")

    logger.info(f"🤖 Modelo: gpt-5-mini (Responses API)")
    logger.info("=" * 60)

    response = input("▶️  Prosseguir com a Etapa 2 (enviar para GPT-5)? (s/n): ").strip().lower()
    if response not in ["s", "sim", "y", "yes"]:
        logger.info("🛑 Geração cancelada pelo usuário")
        logger.info(f"ℹ️  O arquivo consolidado foi salvo em: {consolidated_path}")
        return consolidated_path

    logger.info("=" * 60)
    logger.info("🤖 Etapa 2: Gerando material de estudo via GPT-5...")
    logger.info("=" * 60)

    study_content = generate_study_content_with_gpt5(
        consolidated,
        api_key,
        language=study_language,
    )

    # Salva material final
    with open(output_path, "w", encoding="utf-8") as f:
        header = (
            f"# Material de Estudo - Playlist (GPT-5)\n"
            f"**Gerado em:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Fonte:** {subtitle_dir}\n\n---\n\n"
        )
        f.write(header + study_content)

    logger.info("=" * 60)
    logger.info(f"✅ Material de estudo salvo: {Path(output_path).name}")
    logger.info(f"📄 Tamanho: {len(study_content):,} caracteres")
    logger.info("=" * 60)

    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate study material from playlist subtitles using GPT-5 (Responses API)",
    )
    parser.add_argument(
        "-s",
        "--subtitle-dir",
        type=str,
        required=True,
        help="Directory containing SRT subtitle files",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file path (default: study_material_gpt5_TIMESTAMP.md)",
    )
    parser.add_argument(
        "-k",
        "--api-key",
        type=str,
        default=os.environ.get("OPENAI_API_KEY"),
        help="OpenAI API key",
    )
    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default="pt",
        choices=["pt", "en"],
        help="Study material language (default: pt)",
    )
    parser.add_argument(
        "--skip-gpt",
        action="store_true",
        help="Only consolidate subtitles, skip GPT generation",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Ask confirmation for large playlists (mantido para compat, não usado)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(message)s", handlers=[logging.StreamHandler()])

    if not args.skip_gpt and not args.api_key:
        logger.error("❌ OpenAI API key required (use --api-key or OPENAI_API_KEY)")
        raise SystemExit(1)

    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"study_material_gpt5_{timestamp}.md"

    try:
        result = generate_playlist_study_content_gpt5(
            subtitle_dir=args.subtitle_dir,
            output_path=args.output,
            api_key=args.api_key or "",
            study_language=args.language,
            skip_gpt=args.skip_gpt,
            interactive=args.interactive,
        )
        if result:
            logger.info("✨ Concluído!")
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        raise SystemExit(1)
