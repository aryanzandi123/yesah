# Fix for RHEB-MTOR Interaction Not Showing Up

## Problem Summary

The RHEB → MTOR direct interaction is not appearing in the visualization for ATXN3, even though:
1. The `validate_existing_arrows.py` script validated it and saved it to the database (ID: 17)
2. The ATXN3 → MTOR indirect interaction has both `direct_arrow: activates` and `net_arrow: inhibits` in its function data
3. The data exists in the arrow validation JSON logs

## Root Cause Analysis

The issue is in `app.py:build_full_json_from_db()` function. Here's what happens:

### Current Flow for ATXN3 Query:

1. **Step 1 (lines 404-407)**: Query interactions where ATXN3 is protein_a or protein_b
   - ✓ Finds: ATXN3-RHEB (direct)
   - ✓ Finds: ATXN3-MTOR (indirect, mediator=RHEB)
   - ✗ Does NOT find: RHEB-MTOR (neither protein is ATXN3)

2. **Step 2 (lines 414-578)**: Process direct interactions
   - ✓ Adds ATXN3-RHEB to interactions_list
   - ✓ Adds RHEB to interactor_proteins
   - ✓ Adds ATXN3-MTOR to interactions_list
   - ✓ Adds MTOR to interactor_proteins

3. **Step 3 (lines 580-682)**: Retrieve chain links for indirect interactions
   - For ATXN3-MTOR (indirect, mediator_chain=['RHEB']):
     - mediator_symbol = 'RHEB'
     - target_protein = MTOR
     - **Queries for RHEB ↔ MTOR interaction**
     - ✓ Should find it and add to interactions_list
     - **BUT**: This is where it might fail!

4. **Step 4 (lines 684-786)**: Query shared interactions
   - Queries for interactions where both proteins are in [RHEB, MTOR]
   - ✓ Finds RHEB-MTOR
   - **BUT**: Lines 718-723 SKIP it because (RHEB, MTOR) is in indirect_chain_pairs!

### The Problem:

**Step 3 should add RHEB-MTOR as a chain link, but it's failing.**

Possible reasons:
1. The chain link query might not find RHEB-MTOR
2. The RHEB-MTOR interaction might have the wrong properties (e.g., interaction_type='indirect' instead of 'direct')
3. There might be a database consistency issue

**Step 4 explicitly excludes RHEB-MTOR** because it's part of the indirect chain (lines 718-723).

## Solution

We need to fix **Step 3** to ensure chain links are properly added, AND we need to ensure the RHEB-MTOR interaction exists in the database with the correct properties.

### Fix 1: Improve Chain Link Retrieval (app.py lines 580-682)

Add debugging and ensure mediator proteins are added to interactor_proteins even before querying:

```python
# Lines 414-428: After processing each interaction, add mediators to interactor list
# ADD THIS CODE BLOCK after line 428 (after interactor_proteins.append(partner)):

# Also track mediator proteins for indirect interactions
if interaction.interaction_type == "indirect" and interaction.mediator_chain:
    for mediator_symbol in interaction.mediator_chain:
        mediator_protein = Protein.query.filter_by(symbol=mediator_symbol).first()
        if mediator_protein:
            if mediator_protein not in interactor_proteins:
                interactor_proteins.append(mediator_protein)
            protein_set.add(mediator_symbol)
```

### Fix 2: Add Debug Logging to Chain Link Query (lines 594-682)

Modify the chain link query section to add logging:

```python
# Around line 612, ADD logging:
if chain_link and chain_link.id not in chain_link_ids:
    print(f"[DEBUG] Found chain link: {mediator_symbol} → {target_protein.symbol} (ID: {chain_link.id}, type: {chain_link.interaction_type})")
    chain_link_ids.add(chain_link.id)
    # ... rest of code
else:
    if not chain_link:
        print(f"[DEBUG] Chain link NOT found in database: {mediator_symbol} → {target_protein.symbol}")
    elif chain_link.id in chain_link_ids:
        print(f"[DEBUG] Chain link already processed: {mediator_symbol} → {target_protein.symbol} (ID: {chain_link.id})")
```

### Fix 3: Ensure RHEB-MTOR Exists with Correct Properties

Create a script to verify and fix the RHEB-MTOR interaction in the database:

```python
# Check if RHEB-MTOR exists
rheb = Protein.query.filter_by(symbol='RHEB').first()
mtor = Protein.query.filter_by(symbol='MTOR').first()

if rheb and mtor:
    # Query for interaction (respecting canonical ordering)
    if rheb.id < mtor.id:
        interaction = Interaction.query.filter_by(
            protein_a_id=rheb.id,
            protein_b_id=mtor.id
        ).first()
    else:
        interaction = Interaction.query.filter_by(
            protein_a_id=mtor.id,
            protein_b_id=rheb.id
        ).first()

    if interaction:
        print(f"Found RHEB-MTOR interaction (ID: {interaction.id})")
        print(f"  interaction_type: {interaction.interaction_type}")
        print(f"  discovered_in_query: {interaction.discovered_in_query}")
        print(f"  function_context: {interaction.function_context}")

        # Fix if needed
        if interaction.interaction_type != 'direct':
            print(f"  WARNING: interaction_type is '{interaction.interaction_type}', should be 'direct'")
            interaction.interaction_type = 'direct'
            interaction.data['interaction_type'] = 'direct'
            db.session.commit()
    else:
        print("ERROR: RHEB-MTOR interaction does NOT exist in database!")
```

### Fix 4: Alternative - Don't Exclude Chain Links from Shared Interactions

If the chain link query is working but the shared interaction query is excluding it, we could modify the exclusion logic:

```python
# Lines 718-723: MODIFY to NOT exclude chain links that have function_context='direct'
for shared_ix in shared_interactions:
    protein_a_sym = shared_ix.protein_a.symbol
    protein_b_sym = shared_ix.protein_b.symbol

    # Check if this is a chain link with direct context
    is_direct_chain_link = (
        shared_ix.function_context == 'direct' and
        shared_ix.data.get('_inferred_from_chain')
    )

    # Skip indirect chain pairs UNLESS it's a direct chain link (RHEB-MTOR)
    if not is_direct_chain_link:
        if (protein_a_sym, protein_b_sym) in indirect_chain_pairs or (protein_b_sym, protein_a_sym) in indirect_chain_pairs:
            continue  # Don't add to shared links

    # ... rest of code to add shared interaction
```

## Implementation Plan

1. ✅ Create diagnostic script to understand the issue
2. ⏳ Add Fix 1: Track mediator proteins in interactor_proteins
3. ⏳ Add Fix 2: Add debug logging to chain link query
4. ⏳ Create and run Fix 3: Verify and fix RHEB-MTOR in database
5. ⏳ Test with build_full_json_from_db('ATXN3')
6. ⏳ If still not working, apply Fix 4
7. ⏳ Remove debug logging after confirming fix works

## Expected Outcome

After applying these fixes, when querying for ATXN3:
- ✓ ATXN3-RHEB direct interaction appears
- ✓ ATXN3-MTOR indirect interaction appears with net_arrow=inhibits
- ✓ **RHEB-MTOR direct interaction appears** with direct_arrow=activates
- ✓ Table view shows both direct and net effects
- ✓ Graph view displays all three interactions with correct arrows
