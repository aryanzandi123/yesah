# CRITICAL FIX: Dual-Track Function Display

## Problem
For indirect interactions (Query → Mediator → Target), only NET EFFECT functions were showing, not DIRECT functions.

Example:
- **ATXN3 → RHEB → MTOR** (indirect chain)
- ✓ Shows: "ATXN3 inhibits mTOR [Net Effect]"
- ✗ **MISSING**: "RHEB activates mTOR [Direct]"

## Solution Created

### 1. New Script: `scripts/enrich_mediator_pairs.py`

**Purpose**: For EVERY indirect interaction, research and enrich the mediator-target direct pair.

**Features**:
- ✓ Uses Gemini 2.5 Pro with extended thinking (32K tokens)
- ✓ Google Search grounding enabled
- ✓ Fills out COMPLETE function data:
  - Biological cascade (step-by-step)
  - Cellular process (detailed mechanism)
  - Evidence (primary papers with PMIDs)
  - Specific effects
  - Relevant quotes
- ✓ Contextually relevant to chain function
- ✓ Describes NORMAL pair interaction (independent of chain)

**Usage**:
```bash
# Process all proteins (dry-run)
python3 scripts/enrich_mediator_pairs.py --dry-run --verbose

# Process specific protein (ATXN3)
python3 scripts/enrich_mediator_pairs.py --protein ATXN3 --verbose

# Apply changes to database
python3 scripts/enrich_mediator_pairs.py --protein ATXN3

# Quick fix
./FIX_NOW.sh
```

### 2. Fixed: app.py (3 critical fixes)

**Fix 1 (Lines 430-439)**: Track mediator proteins in interactor_proteins list
- Ensures mediators are included in shared link queries

**Fix 2 (Lines 623-637)**: Proper chain link retrieval
- Finds mediator→target direct interactions from chains
- Adds them to visualization

**Fix 3 (Lines 740-756)**: Allow direct chain links in shared interactions
- Checks `function_context='direct'` flag
- Includes direct chain links even if part of indirect chain
- Prevents duplicates by checking `chain_link_ids`

### 3. Fixed: Duplicate Link Warnings

**Problem**: Chain links being added twice
**Solution**: Check `shared_ix.id in chain_link_ids` before adding in shared section

## Expected Result

After running the enrichment script:

### For ATXN3 → RHEB → MTOR:

**Table View**:
```
RHEB ↔ MTOR
├─ Function: mTORC1 Signaling [Net Effect]
│  Arrow: inhibits
│  Context: ATXN3 inhibits RHEB, thus inhibits mTOR activation
│  Cascade: ATXN3 → RHEB deubiquitination → reduced mTOR binding → ...
│
└─ Function: mTORC1 Signaling [Direct]
   Arrow: activates  ← THIS IS NEW!
   Context: RHEB normally activates mTOR kinase
   Cascade: RHEB-GTP → mTOR binding → allosteric activation → ...
```

**Graph View**:
- Two separate edges between RHEB and MTOR nodes
  - One dashed (indirect/net effect): inhibits
  - One solid (direct): activates

## How It Works

### Phase 1: Enrichment Script
1. Query all indirect interactions from database
2. For each: identify mediator and target
3. Extract function context from chain (e.g., "mTORC1 Signaling")
4. Use Gemini to research mediator→target DIRECT interaction:
   - Prompt: "How does RHEB normally affect MTOR in mTORC1 signaling?"
   - Search: Primary research papers
   - Output: Complete function data
5. Add enriched function to database with `function_context='direct'`

### Phase 2: Visualization (app.py)
1. Query ATXN3 interactions
2. Find ATXN3-MTOR (indirect, with net effect)
3. Find ATXN3-RHEB (direct)
4. **NEW**: Find RHEB-MTOR (direct, from chain link query OR shared query)
5. Display all three in graph/table

### Phase 3: Dual-Track Display
- Visualizer checks `function_context` field:
  - `'net'`: Shows [Net Effect] badge
  - `'direct'`: Shows [Direct] badge or no badge
- Both appear as separate function rows in table
- Both appear in modals/function displays

## Running The Fix

### Option 1: Quick Fix (Recommended)
```bash
./FIX_NOW.sh
```

### Option 2: Manual
```bash
# Test first (dry-run)
python3 scripts/enrich_mediator_pairs.py --protein ATXN3 --verbose --dry-run

# Apply changes
python3 scripts/enrich_mediator_pairs.py --protein ATXN3 --verbose

# Check results
# Visit http://localhost:5000/api/visualize/ATXN3
```

### Option 3: Enrich All Proteins
```bash
# This will take a while (uses Gemini for each indirect interaction)
python3 scripts/enrich_mediator_pairs.py --verbose
```

## Verification

After running the script, check:

1. **Database**: Query for RHEB-MTOR interaction
   ```python
   python3 verify_fix_rheb_mtor.py
   ```
   Should show:
   - `interaction_type = 'direct'`
   - `function_context = 'direct'`
   - Functions array has both net and direct entries

2. **Visualization**: Load ATXN3
   - Graph should show RHEB-MTOR edge
   - Table should show two function rows for RHEB-MTOR
   - Modal should show complete data for both

3. **Console**: No duplicate link warnings

## Technical Details

### Function Context Field
- `'net'`: Function describes net effect through chain
- `'direct'`: Function describes normal pair interaction
- `null`: Legacy/unvalidated (treated as mixed)

### Interaction Type Field
- `'direct'`: Physical/direct interaction
- `'indirect'`: Cascade/pathway (requires mediator)

### Discovery Method Field
- `'pipeline'`: Found by main pipeline
- `'indirect_chain_extraction'`: Extracted from chain by enrichment script
- `'requery'`: Found by requery

### Markers
- `_enriched_by_script`: Added by enrichment script
- `_inferred_from_chain`: Extracted from indirect chain
- `_display_badge`: Visual marker for frontend

## Files Changed

1. **scripts/enrich_mediator_pairs.py** (NEW)
   - Main enrichment script

2. **FIX_NOW.sh** (NEW)
   - Quick runner for ATXN3

3. **app.py**
   - Lines 430-439: Track mediators
   - Lines 623-637: Chain link retrieval
   - Lines 740-756: Shared link filtering

4. **CRITICAL_FIX_README.md** (NEW)
   - This file

## Next Steps

1. Run `./FIX_NOW.sh`
2. Check ATXN3 visualization
3. Verify dual-track display works
4. Run for all proteins if successful
5. Remove enrichment script from repo (or keep for future use)
