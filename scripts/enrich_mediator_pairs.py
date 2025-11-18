#!/usr/bin/env python3
"""
Mediator-Pair Function Enrichment Script
=========================================

For EVERY indirect interaction (Query → Mediator → Target), this script:
1. Identifies the mediator-target pair
2. Creates/enriches a DIRECT interaction between them
3. Fills out COMPLETE function data (biological cascade, evidence, etc.)
4. Describes the NORMAL pair interaction (independent of chain)
5. Keeps it contextually relevant to the affected function

Example:
- Chain: ATXN3 → RHEB → MTOR (net effect: ATXN3 inhibits mTOR signaling)
- Creates: RHEB → MTOR direct interaction
- Function: RHEB activates mTOR signaling (normal behavior)
- Context: mTOR signaling (from chain)
- Output: Full biological cascade of how RHEB normally activates mTOR

Uses Gemini 2.5 Pro with extended thinking + Google Search grounding.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from models import db, Protein, Interaction
from app import app

# Gemini imports
try:
    from google import genai as google_genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[ERROR] google-genai not installed. Cannot run enrichment.")
    sys.exit(1)


# Constants - Match runner.py configuration
MAX_THINKING_TOKENS = 32768  # Extended thinking budget
MAX_OUTPUT_TOKENS = 65536    # Match runner.py
TEMPERATURE = 0.3            # Match runner.py
TOP_P = 0.90                 # Match runner.py
MAX_WORKERS = 3              # Conservative for complex queries

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def call_gemini_with_thinking(
    prompt: str,
    api_key: str,
    system_instruction: str = "",
    response_format: str = "json",
    max_retries: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Call Gemini 2.5 Pro with thinking budget and Google Search (matches runner.py config).

    Args:
        prompt: User prompt
        api_key: Google AI API key
        system_instruction: System instruction
        response_format: "json" or "text"
        max_retries: Number of retries on failure

    Returns:
        Parsed JSON response or None on failure
    """
    client = google_genai.Client(api_key=api_key)

    # Configure thinking mode - Match runner.py pattern
    thinking_config = types.ThinkingConfig(
        thinking_budget=MAX_THINKING_TOKENS,
        include_thoughts=True
    )

    # Configure generation - Match runner.py configuration
    config_args = {
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "thinking_config": thinking_config,
        "response_modalities": ["TEXT"],
        "safety_settings": [
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF"
            )
        ],
        "tools": [types.Tool(google_search=types.GoogleSearch())]  # Enable Google Search
        # NOTE: Cannot use response_mime_type with tools - parse JSON manually from text response
    }

    config = types.GenerateContentConfig(**config_args)

    # Use gemini-2.5-pro like runner.py
    model_name = "gemini-2.5-pro"

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )

            if response_format == "json":
                # Parse JSON response
                text = response.text.strip()
                # Remove markdown code blocks if present
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

                return json.loads(text)
            else:
                return {"text": response.text}

        except Exception as e:
            print(f"[ERROR] Gemini call failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return None

    return None


def extract_function_context(indirect_interaction: Dict[str, Any]) -> Tuple[str, str]:
    """
    Extract the function name and context from an indirect interaction.

    Args:
        indirect_interaction: Indirect interaction data

    Returns:
        (function_name, function_context) tuple
    """
    functions = indirect_interaction.get("data", {}).get("functions", [])

    if not functions:
        return ("Unknown Function", "general cellular processes")

    # Get primary function (first one, or one with most detail)
    primary_func = max(functions, key=lambda f: len(f.get("cellular_process", "")))

    function_name = primary_func.get("function", "Unknown Function")

    # Build context from cellular process and biological consequence
    cellular_process = primary_func.get("cellular_process", "")
    bio_consequence = primary_func.get("biological_consequence", [])

    if cellular_process:
        function_context = cellular_process
    elif bio_consequence and len(bio_consequence) > 0:
        function_context = bio_consequence[0]
    else:
        function_context = f"{function_name} regulation"

    return (function_name, function_context)


def enrich_mediator_target_pair(
    mediator: str,
    target: str,
    function_name: str,
    function_context: str,
    api_key: str,
    verbose: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Use Gemini to research and create complete function data for mediator→target pair.

    This describes the NORMAL interaction between the pair, independent of chain context,
    but contextually relevant to the affected function.

    Args:
        mediator: Mediator protein symbol (e.g., "RHEB")
        target: Target protein symbol (e.g., "MTOR")
        function_name: Function affected in chain (e.g., "mTORC1 Signaling")
        function_context: Context from chain (e.g., "RHEB activates mTOR kinase...")
        api_key: Google AI API key
        verbose: Enable detailed logging

    Returns:
        Complete function dict with all fields filled out
    """
    if verbose:
        print(f"    [ENRICH] Researching {mediator} → {target} interaction")
        print(f"             Function context: {function_name}")

    system_instruction = f"""You are an expert molecular biologist specializing in protein-protein interactions.

Your task: Research and describe the DIRECT interaction between {mediator} and {target} proteins.

CRITICAL REQUIREMENTS:
1. Describe the NORMAL interaction between {mediator} and {target} (independent of any upstream regulators)
2. Focus on how {mediator} affects {target} in the context of: {function_name}
3. Use Google Search to find primary research papers
4. Provide COMPLETE data with all fields filled out
5. Include biological cascade, cellular process, evidence, PMIDs
6. Be comprehensive - this is for a scientific database

Context: This pair is part of a larger signaling chain, but you should describe their DIRECT relationship,
not the net effect through the chain.
"""

    prompt = f"""Research the direct protein-protein interaction between {mediator} and {target}.

**Target Function Context**: {function_name}
**Background**: {function_context}

Your task is to describe how {mediator} NORMALLY interacts with {target} (independent of upstream regulators).

Use Google Search to find primary research papers about {mediator}-{target} interaction.

Return a JSON object with this EXACT structure:

{{
  "function": "{function_name}",
  "arrow": "activates|inhibits|binds|regulates",
  "direction": "main_to_primary",
  "cellular_process": "Detailed description of the molecular mechanism...",
  "effect_description": "Description of the biological effect...",
  "biological_consequence": [
    "Step 1 of cascade",
    "Step 2 of cascade",
    "..."
  ],
  "specific_effects": [
    "Specific effect 1",
    "Specific effect 2",
    "..."
  ],
  "evidence": [
    {{
      "pmid": "12345678",
      "doi": "10.1234/...",
      "paper_title": "...",
      "authors": "...",
      "journal": "...",
      "year": 2020,
      "species": "human",
      "assay": "Co-IP, Western blot, ...",
      "relevant_quote": "..."
    }}
  ],
  "pmids": ["12345678", "87654321"],
  "confidence": 0.85
}}

CRITICAL:
- "arrow" must reflect {mediator}'s NORMAL effect on {target} (NOT net effect through chain)
- "cellular_process" should be detailed (100-200 words)
- "biological_consequence" should be a step-by-step cascade (5-10 steps)
- "specific_effects" should list specific molecular events (5-10 items)
- "evidence" must include at least 2-3 primary research papers with PMIDs
- "relevant_quote" should be actual quotes from papers

Focus on {function_name} but describe the normal {mediator}→{target} relationship.
"""

    result = call_gemini_with_thinking(
        prompt=prompt,
        api_key=api_key,
        system_instruction=system_instruction,
        response_format="json"
    )

    if not result:
        if verbose:
            print(f"    [ENRICH] Failed to get response from Gemini")
        return None

    # Validate required fields
    required_fields = ["function", "arrow", "cellular_process", "biological_consequence", "specific_effects"]
    for field in required_fields:
        if field not in result or not result[field]:
            if verbose:
                print(f"    [ENRICH] Missing required field: {field}")
            return None

    # Add metadata
    result["_enriched_by_script"] = True
    result["_enriched_at"] = datetime.utcnow().isoformat()
    result["function_context"] = "direct"  # Mark as direct (not net effect)

    if verbose:
        print(f"    [ENRICH] ✓ Successfully enriched with {len(result.get('evidence', []))} papers")
        print(f"             Arrow: {result.get('arrow', 'unknown')}")
        print(f"             Cascade steps: {len(result.get('biological_consequence', []))}")

    return result


def process_indirect_interaction(
    interaction_data: Dict[str, Any],
    api_key: str,
    verbose: bool = False,
    dry_run: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Process one indirect interaction to enrich its mediator-target pair.

    Args:
        interaction_data: Indirect interaction data
        api_key: Google AI API key
        verbose: Enable detailed logging
        dry_run: If True, don't write to database

    Returns:
        Enrichment result or None
    """
    # Extract chain information
    main_protein = interaction_data["main_protein"]
    target_protein = interaction_data["partner_protein"]
    upstream_interactor = interaction_data.get("upstream_interactor")
    mediator_chain = interaction_data.get("mediator_chain", [])

    # Determine mediator
    mediator = upstream_interactor or (mediator_chain[-1] if mediator_chain else None)

    if not mediator:
        if verbose:
            print(f"  [SKIP] No mediator found for {main_protein} → {target_protein}")
        return None

    print(f"\n  Processing: {main_protein} → {mediator} → {target_protein}")

    # Extract function context from the indirect interaction
    function_name, function_context = extract_function_context(interaction_data)

    print(f"    Function: {function_name}")
    print(f"    Researching direct pair: {mediator} → {target_protein}")

    # Enrich the mediator-target pair
    enriched_function = enrich_mediator_target_pair(
        mediator=mediator,
        target=target_protein,
        function_name=function_name,
        function_context=function_context,
        api_key=api_key,
        verbose=verbose
    )

    if not enriched_function:
        return None

    # Check if mediator-target interaction exists in database
    with app.app_context():
        mediator_protein = Protein.query.filter_by(symbol=mediator).first()
        target_protein_obj = Protein.query.filter_by(symbol=target_protein).first()

        if not mediator_protein or not target_protein_obj:
            print(f"    [ERROR] Protein not found in database: {mediator} or {target_protein}")
            return None

        # Query for existing interaction
        if mediator_protein.id < target_protein_obj.id:
            existing = db.session.query(Interaction).filter(
                Interaction.protein_a_id == mediator_protein.id,
                Interaction.protein_b_id == target_protein_obj.id
            ).first()
        else:
            existing = db.session.query(Interaction).filter(
                Interaction.protein_a_id == target_protein_obj.id,
                Interaction.protein_b_id == mediator_protein.id
            ).first()

        if existing:
            print(f"    [UPDATE] Interaction exists (ID: {existing.id}), adding enriched function")

            # Add enriched function to existing interaction
            data = existing.data.copy()
            if "functions" not in data:
                data["functions"] = []

            # Check if function already exists (avoid duplicates)
            existing_funcs = [f.get("function") for f in data["functions"]]
            if function_name in existing_funcs:
                # Update existing function
                for i, func in enumerate(data["functions"]):
                    if func.get("function") == function_name and func.get("function_context") == "direct":
                        data["functions"][i] = enriched_function
                        break
                else:
                    # No direct version exists, add it
                    data["functions"].append(enriched_function)
            else:
                # Add new function
                data["functions"].append(enriched_function)

            # Ensure interaction properties are correct
            data["interaction_type"] = "direct"
            data["function_context"] = "direct"

            if not dry_run:
                existing.data = data
                existing.interaction_type = "direct"
                existing.function_context = "direct"
                existing.updated_at = datetime.utcnow()
                db.session.commit()
                print(f"    [UPDATE] ✓ Updated database")
            else:
                print(f"    [DRY-RUN] Would update database")
        else:
            print(f"    [CREATE] Interaction does not exist, creating new entry")

            # CREATE new direct interaction
            # Determine canonical ordering
            if mediator_protein.id < target_protein_obj.id:
                protein_a_id = mediator_protein.id
                protein_b_id = target_protein_obj.id
                # mediator → target means a → b
                direction = "a_to_b"
            else:
                protein_a_id = target_protein_obj.id
                protein_b_id = mediator_protein.id
                # mediator → target means b → a
                direction = "b_to_a"

            # Build interaction data
            interaction_data_new = {
                "primary": target_protein,
                "direction": "main_to_primary",  # From mediator's perspective
                "arrow": enriched_function.get("arrow", "activates"),
                "interaction_type": "direct",
                "function_context": "direct",
                "functions": [enriched_function],
                "evidence": enriched_function.get("evidence", []),
                "pmids": enriched_function.get("pmids", []),
                "confidence": enriched_function.get("confidence", 0.75),
                "_inferred_from_chain": True,
                "_enriched_by_script": True,
                "_original_chain": f"{main_protein}→{mediator}→{target_protein}"
            }

            if not dry_run:
                # Create new Interaction record
                new_interaction = Interaction(
                    protein_a_id=protein_a_id,
                    protein_b_id=protein_b_id,
                    confidence=interaction_data_new.get("confidence", 0.75),
                    direction=direction,
                    arrow=enriched_function.get("arrow", "activates"),
                    data=interaction_data_new,
                    discovered_in_query=main_protein,
                    discovery_method="mediator_pair_enrichment",
                    interaction_type="direct",
                    function_context="direct",
                    upstream_interactor=None,
                    mediator_chain=None,
                    depth=1,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                db.session.add(new_interaction)
                db.session.commit()
                print(f"    [CREATE] ✓ Created new interaction (ID: {new_interaction.id})")
            else:
                print(f"    [DRY-RUN] Would create new interaction")

    return enriched_function


def enrich_protein_mediator_pairs(
    protein_symbol: str,
    api_key: str,
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Enrich mediator-target pairs for a specific protein (programmatic interface).

    Args:
        protein_symbol: Protein to process (e.g., "ATXN3")
        api_key: Google AI API key
        verbose: Enable verbose logging
        dry_run: Don't write to database

    Returns:
        Stats dict with enrichment counts
    """
    with app.app_context():
        # Find protein
        protein = Protein.query.filter_by(symbol=protein_symbol).first()
        if not protein:
            print(f"[ENRICH] Protein '{protein_symbol}' not found in database", file=sys.stderr)
            return {"pairs_enriched": 0}

        # Query indirect interactions for this protein
        query = Interaction.query.filter_by(interaction_type="indirect").filter(
            (Interaction.protein_a_id == protein.id) |
            (Interaction.protein_b_id == protein.id)
        )

        interactions = query.all()

        if not interactions:
            print(f"[ENRICH] No indirect interactions found for {protein_symbol}", file=sys.stderr)
            return {"pairs_enriched": 0}

        pairs_enriched = 0

        for interaction in interactions:
            # Extract chain
            mediator_chain = interaction.mediator_chain
            if not mediator_chain or len(mediator_chain) == 0:
                continue

            # Get target protein
            target_protein_id = interaction.protein_b_id if interaction.protein_a_id == protein.id else interaction.protein_a_id
            target_protein = db.session.get(Protein, target_protein_id)
            if not target_protein:
                continue

            # Process each mediator-target pair
            for mediator_symbol in mediator_chain:
                # Get function context from interaction
                functions = interaction.data.get("functions", [])
                if not functions:
                    continue

                function_name = functions[0].get("function", "Unknown Function")
                function_context = functions[0].get("biological_consequence", "")

                # Enrich this pair
                try:
                    enriched_function = enrich_mediator_target_pair(
                        mediator=mediator_symbol,
                        target=target_protein.symbol,
                        function_name=function_name,
                        function_context=function_context,
                        api_key=api_key,
                        verbose=verbose,
                        dry_run=dry_run
                    )

                    if enriched_function:
                        pairs_enriched += 1

                except Exception as e:
                    if verbose:
                        print(f"[ENRICH] Error enriching {mediator_symbol}→{target_protein.symbol}: {e}", file=sys.stderr)

        db.session.commit()

        return {"pairs_enriched": pairs_enriched}


def main():
    parser = argparse.ArgumentParser(description="Enrich mediator-target pairs with complete function data")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to database")
    parser.add_argument("--protein", type=str, help="Only process specific protein's indirect interactions")
    parser.add_argument("--limit", type=int, help="Limit number of pairs to process")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    # Load environment
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY not set in environment")
        sys.exit(1)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n{'='*80}")
    print(f"MEDIATOR-PAIR FUNCTION ENRICHMENT ({mode})")
    print(f"{'='*80}\n")

    # Query indirect interactions
    with app.app_context():
        query = Interaction.query.filter_by(interaction_type="indirect")

        if args.protein:
            protein = Protein.query.filter_by(symbol=args.protein).first()
            if not protein:
                print(f"[ERROR] Protein '{args.protein}' not found")
                sys.exit(1)
            query = query.filter(
                (Interaction.protein_a_id == protein.id) |
                (Interaction.protein_b_id == protein.id)
            )
            print(f"[INFO] Filtering to protein: {args.protein}")

        if args.limit:
            query = query.limit(args.limit)
            print(f"[INFO] Limiting to {args.limit} interactions")

        interactions = query.all()

        if not interactions:
            print("[INFO] No indirect interactions found")
            sys.exit(0)

        print(f"[INFO] Found {len(interactions)} indirect interactions to process\n")

        # Extract data
        interaction_data_list = []
        for interaction in interactions:
            protein_a = db.session.get(Protein, interaction.protein_a_id)
            protein_b = db.session.get(Protein, interaction.protein_b_id)

            main_protein = interaction.discovered_in_query or protein_a.symbol
            partner_protein = protein_b.symbol if main_protein == protein_a.symbol else protein_a.symbol

            interaction_data_list.append({
                "id": interaction.id,
                "data": interaction.data,
                "main_protein": main_protein,
                "partner_protein": partner_protein,
                "upstream_interactor": interaction.upstream_interactor,
                "mediator_chain": interaction.mediator_chain or [],
                "interaction_type": "indirect"
            })

        # Process each indirect interaction
        enriched_count = 0
        failed_count = 0

        for idx, interaction_data in enumerate(interaction_data_list):
            print(f"\n[{idx+1}/{len(interaction_data_list)}]")

            try:
                result = process_indirect_interaction(
                    interaction_data,
                    api_key,
                    verbose=args.verbose,
                    dry_run=args.dry_run
                )

                if result:
                    enriched_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                print(f"  [ERROR] Failed: {e}")
                failed_count += 1

        # Summary
        print(f"\n{'='*80}")
        print(f"ENRICHMENT COMPLETE")
        print(f"{'='*80}")
        print(f"Total processed: {len(interaction_data_list)}")
        print(f"Successfully enriched: {enriched_count}")
        print(f"Failed: {failed_count}")

        if args.dry_run:
            print(f"\n[DRY-RUN] No changes written to database")
        else:
            print(f"\n[LIVE] Changes written to database")

        print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
