#!/usr/bin/env python3
"""
Diagnostic script to understand the RHEB-MTOR interaction issue.

This script will:
1. Check what interactions exist in the database
2. Show how build_full_json_from_db processes them
3. Identify why RHEB-MTOR direct interaction isn't showing up
"""
import json

# Mock the database interactions based on what we know
# This simulates what should be in the database

print("="*80)
print("DIAGNOSTIC: RHEB-MTOR Interaction Issue")
print("="*80)

print("\n1. EXPECTED DATABASE STATE:")
print("-" * 80)

print("\nInteraction 1: ATXN3 ↔ RHEB (Direct)")
print("  - discovered_in_query: ATXN3")
print("  - interaction_type: direct")
print("  - This is the direct ATXN3-RHEB interaction")

print("\nInteraction 2: ATXN3 → MTOR (Indirect)")
print("  - discovered_in_query: ATXN3")
print("  - interaction_type: indirect")
print("  - upstream_interactor: RHEB")
print("  - mediator_chain: ['RHEB']")
print("  - functions[0]:")
print("    - function: mTORC1 Signaling")
print("    - arrow: inhibits (NET effect)")
print("    - direct_arrow: activates (RHEB→MTOR)")
print("    - net_arrow: inhibits (ATXN3→MTOR via RHEB)")
print("    - function_context: net")

print("\nInteraction 3: RHEB → MTOR (Direct)")
print("  - discovered_in_query: ATXN3 (extracted from chain)")
print("  - interaction_type: direct")
print("  - function_context: direct")
print("  - This is the direct RHEB-MTOR link extracted from the chain")

print("\n" + "="*80)
print("2. HOW build_full_json_from_db SHOULD PROCESS (for query='ATXN3'):")
print("-" * 80)

print("\nStep 1: Query interactions where ATXN3 is protein_a or protein_b")
print("  → Found: Interaction 1 (ATXN3-RHEB) ✓")
print("  → Found: Interaction 2 (ATXN3-MTOR) ✓")
print("  → NOT Found: Interaction 3 (RHEB-MTOR) ✗ (neither protein is ATXN3)")

print("\nStep 2: Process direct interactions (lines 414-578)")
print("  → Interaction 1 (ATXN3-RHEB): Added to interactions_list ✓")
print("  → interactor_proteins.append(RHEB)")
print("  → Interaction 2 (ATXN3-MTOR): Added to interactions_list ✓")
print("  → interactor_proteins.append(MTOR)")

print("\nStep 3: Retrieve chain links for indirect interactions (lines 580-682)")
print("  → For Interaction 2 (ATXN3-MTOR, indirect):")
print("    - mediator_chain = ['RHEB']")
print("    - target_protein = MTOR")
print("    - Query for RHEB ↔ MTOR interaction...")
print("    - Should find Interaction 3 (RHEB-MTOR) ✓")
print("    - Add to interactions_list with source=RHEB, target=MTOR ✓")

print("\nStep 4: Query shared interactions (lines 684-770)")
print("  → interactor_ids = [RHEB.id, MTOR.id]")
print("  → Query for interactions where both proteins are in interactor_ids")
print("  → Exclude main protein (ATXN3)")
print("  → Should find: Interaction 3 (RHEB-MTOR) ✓")
print("  → But might be duplicate if already added in Step 3")

print("\n" + "="*80)
print("3. POTENTIAL ISSUES:")
print("-" * 80)

print("\nISSUE 1: Chain link query might not find RHEB-MTOR")
print("  Reason: Interaction 3 might have interaction_type='indirect' instead of 'direct'")
print("  Solution: Check interaction.interaction_type in database")

print("\nISSUE 2: RHEB might not be in interactor_proteins list")
print("  Reason: If ATXN3-RHEB is indirect, RHEB won't be added at line 427")
print("  Solution: Always add mediator proteins to interactor_proteins")

print("\nISSUE 3: Duplicate detection might be failing")
print("  Reason: chain_link_ids set might not track properly")
print("  Solution: Check chain_link_ids logic")

print("\nISSUE 4: RHEB-MTOR might not exist in database")
print("  Reason: validate_existing_arrows.py might have failed to create it")
print("  Solution: Check database for RHEB-MTOR interaction")

print("\nISSUE 5: RHEB-MTOR might be categorized wrong")
print("  Reason: discovered_in_query might be empty or wrong")
print("  Solution: Check discovered_in_query field")

print("\n" + "="*80)
print("4. RECOMMENDED FIXES:")
print("-" * 80)

print("\nFIX 1: Always add mediators to interactor_proteins (lines 414-428)")
print("  Before line 429, add:")
print("    # Also add mediator chain proteins to interactor list")
print("    if interaction.mediator_chain:")
print("      for mediator_symbol in interaction.mediator_chain:")
print("        mediator_protein = Protein.query.filter_by(symbol=mediator_symbol).first()")
print("        if mediator_protein and mediator_protein not in interactor_proteins:")
print("          interactor_proteins.append(mediator_protein)")
print("          protein_set.add(mediator_symbol)")

print("\nFIX 2: Check if chain link is 'direct' when querying (line 612)")
print("  After finding chain_link, check:")
print("    if chain_link.interaction_type != 'direct':")
print("      print(f'WARNING: Chain link {mediator_symbol}-{target_protein.symbol} is not direct')")

print("\nFIX 3: Improve shared interaction query (line 694)")
print("  Change filter to be more explicit:")
print("    # Query should include chain links that were extracted")

print("\n" + "="*80)
print("5. ACTION ITEMS:")
print("-" * 80)

print("\n1. Create script to query database and check:")
print("   - Does RHEB-MTOR interaction exist?")
print("   - What is its interaction_type?")
print("   - What is its discovered_in_query?")
print("   - What is its function_context?")

print("\n2. Add mediator proteins to interactor_proteins list in app.py")

print("\n3. Ensure chain link query finds RHEB-MTOR")

print("\n4. Add debug logging to see what interactions are being fetched")

print("\n5. Test with build_full_json_from_db('ATXN3') and verify RHEB-MTOR appears")

print("\n" + "="*80)
