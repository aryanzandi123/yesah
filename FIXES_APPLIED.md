# Fixes Applied for RHEB-MTOR Interaction Issue

## Problem

The RHEB → MTOR direct interaction was not appearing in the ATXN3 visualization, even though:
- The validation script (`validate_existing_arrows.py`) had validated it
- The arrow validation logs showed both `direct_arrow: activates` and `net_arrow: inhibits`
- The database had the interaction saved

## Root Causes Identified

### 1. Mediator Proteins Not Tracked in Interactor List
**Location**: `app.py:426-428`

When processing interactions, the code added partner proteins to `interactor_proteins`, but did NOT add mediator proteins from indirect interactions. This meant RHEB wasn't in the interactor list, which affected shared link queries.

**Fix**: Added code to track mediator proteins (lines 430-439):
```python
# CRITICAL FIX: Also track mediator proteins for indirect interactions
if interaction.interaction_type == "indirect" and interaction.mediator_chain:
    for mediator_symbol in interaction.mediator_chain:
        mediator_protein = Protein.query.filter_by(symbol=mediator_symbol).first()
        if mediator_protein:
            if mediator_protein not in interactor_proteins:
                interactor_proteins.append(mediator_protein)
            protein_set.add(mediator_symbol)
```

### 2. Chain Link Query Not Properly Logged
**Location**: `app.py:623-637`

The chain link query (for finding RHEB→MTOR from ATXN3→RHEB→MTOR indirect chain) had no debugging, making it hard to know if it was finding the interaction or not.

**Fix**: Added debug logging:
```python
if chain_link:
    if chain_link.id not in chain_link_ids:
        print(f"[CHAIN LINK] Found: {mediator_symbol} → {target_protein.symbol} (ID: {chain_link.id}, type: {chain_link.interaction_type})")
        # ... rest of code
    else:
        print(f"[CHAIN LINK] Already processed: {mediator_symbol} → {target_protein.symbol} (ID: {chain_link.id})")
else:
    print(f"[CHAIN LINK] NOT FOUND in database: {mediator_symbol} → {target_protein.symbol}")
```

### 3. Shared Link Query Excluded Direct Chain Links
**Location**: `app.py:736-755`

The shared interaction query had logic to EXCLUDE interactions that were part of indirect chains (lines 718-723 in original). This was correct for true indirect interactions, but it also excluded **direct chain links** like RHEB-MTOR that were extracted from chains.

**Fix**: Modified exclusion logic to allow direct chain links:
```python
# Check if this is a DIRECT chain link (e.g., RHEB-MTOR extracted from ATXN3→RHEB→MTOR)
is_direct_chain_link = (
    shared_ix.function_context == 'direct' and
    (shared_ix.data.get('_inferred_from_chain') or
     shared_ix.discovery_method == 'indirect_chain_extraction')
)

# Skip if this interaction is part of an indirect chain in THIS query
# UNLESS it's a direct chain link (which we want to show)
if not is_direct_chain_link:
    if (protein_a_sym, protein_b_sym) in indirect_chain_pairs or (protein_b_sym, protein_a_sym) in indirect_chain_pairs:
        print(f"[SHARED LINK] Skipping (part of indirect chain): {protein_a_sym} ↔ {protein_b_sym}")
        continue
else:
    print(f"[SHARED LINK] Including direct chain link: {protein_a_sym} → {protein_b_sym} (ID: {shared_ix.id})")
```

### 4. RHEB-MTOR Interaction May Have Wrong Properties
**Location**: Database (interactions table)

The RHEB-MTOR interaction might have:
- `interaction_type = 'indirect'` instead of `'direct'`
- `function_context != 'direct'`
- `upstream_interactor` or `mediator_chain` set (shouldn't be for direct)

**Fix**: Created `verify_fix_rheb_mtor.py` script to check and fix these properties automatically.

## Files Modified

1. **app.py** (3 edits)
   - Line 430-439: Track mediator proteins in interactor_proteins list
   - Line 623-637: Add debug logging for chain link queries
   - Line 736-755: Fix shared link exclusion logic to allow direct chain links

2. **verify_fix_rheb_mtor.py** (new script)
   - Checks if RHEB-MTOR interaction exists
   - Verifies it has correct properties
   - Fixes any issues automatically

## Testing Plan

1. Run `verify_fix_rheb_mtor.py` to ensure RHEB-MTOR is correctly configured
2. Query for ATXN3 via the API or web interface
3. Check console logs for debug output:
   - Should see `[CHAIN LINK] Found: RHEB → MTOR`
   - OR see `[SHARED LINK] Including direct chain link: RHEB → MTOR`
4. Verify visualization shows:
   - ATXN3-RHEB direct interaction
   - ATXN3-MTOR indirect interaction (net effect: inhibits)
   - RHEB-MTOR direct interaction (direct effect: activates)
5. Check table view shows both direct and net arrows for mTORC1 Signaling function

## Expected Behavior After Fix

### Graph View
- Three nodes: ATXN3, RHEB, MTOR
- Three interactions:
  1. ATXN3 ↔ RHEB (direct, binding/inhibition)
  2. ATXN3 → MTOR (indirect, dashed line, inhibits - net effect)
  3. RHEB → MTOR (direct, solid line, activates - direct effect)

### Table View
For the mTORC1 Signaling function:
- ATXN3 → MTOR: Shows net_arrow = inhibits (via RHEB)
- RHEB → MTOR: Shows direct_arrow = activates

### Function Modal
When clicking on ATXN3-MTOR interaction:
- Should show `arrow_context` with both `direct_arrow` and `net_arrow`
- Should explain the chain: ATXN3 inhibits RHEB, RHEB activates MTOR, so net effect is ATXN3 inhibits MTOR

## Remaining Tasks

1. ✅ Fix app.py to track mediators
2. ✅ Fix app.py to allow direct chain links in shared interactions
3. ✅ Add debug logging
4. ✅ Create verification script
5. ⏳ Run verification script
6. ⏳ Test with actual database
7. ⏳ Remove debug logging (or make it conditional with verbose flag)
8. ⏳ Commit and push changes

## Notes for Future

- Debug logging (print statements) should be removed or made conditional with a verbose/debug flag before production
- Consider adding a proper logging framework instead of print statements
- The `function_context` field ('direct' vs 'net') is critical for dual-track system - ensure all interactions have it set correctly
- When creating new interactions from chains, always set:
  - `interaction_type = 'direct'` (for direct mediator links)
  - `function_context = 'direct'`
  - `discovery_method = 'indirect_chain_extraction'`
  - `_inferred_from_chain = True` in data JSONB
