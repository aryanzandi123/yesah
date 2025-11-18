#!/bin/bash
# URGENT FIX: Enrich all mediator-target pairs for ATXN3

echo "=================================="
echo "URGENT FIX: Enriching Mediator Pairs"
echo "=================================="
echo ""
echo "This will:"
echo "1. Find all indirect interactions for ATXN3"
echo "2. Research the mediator-target pairs (e.g., RHEB-MTOR)"
echo "3. Add DIRECT function rows with complete data"
echo "4. Keep NET EFFECT rows for chain context"
echo ""
echo "Running enrichment script..."
echo ""

python3 scripts/enrich_mediator_pairs.py --protein ATXN3 --verbose

echo ""
echo "=================================="
echo "DONE! Check your visualization now."
echo "=================================="
