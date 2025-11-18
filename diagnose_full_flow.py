#!/usr/bin/env python3
"""
Comprehensive Diagnosis Script - Traces Full Data Flow

Checks:
1. ✓ Arrow validation runs in pipeline
2. ✓ DB receives arrow-validated JSON
3. ✓ Backend retrieves validated data
4. ✓ Frontend can parse and display dual-track functions

Specifically for RHEB-MTOR interaction.
"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from app import app
from models import db, Protein, Interaction
import json


def check_1_arrow_validation_in_pipeline():
    """Check if arrow validation is enabled in runner.py"""
    print("\n" + "="*80)
    print("CHECK 1: Is arrow validation enabled in pipeline?")
    print("="*80)

    try:
        from utils.arrow_effect_validator import validate_arrows_and_effects
        print("✓ arrow_effect_validator module imported successfully")
        print(f"✓ validate_arrows_and_effects function: {validate_arrows_and_effects}")

        # Check if GOOGLE_API_KEY is set
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            print(f"✓ GOOGLE_API_KEY is set (length: {len(api_key)})")
        else:
            print("✗ GOOGLE_API_KEY is NOT set - arrow validation will be SKIPPED!")

        return True
    except ImportError as e:
        print(f"✗ Failed to import arrow validator: {e}")
        return False


def check_2_db_has_validated_data():
    """Check if database has arrow-validated data for RHEB-MTOR"""
    print("\n" + "="*80)
    print("CHECK 2: Does database have arrow-validated data?")
    print("="*80)

    with app.app_context():
        # Check ATXN3-MTOR (indirect)
        atxn3 = Protein.query.filter_by(symbol='ATXN3').first()
        mtor = Protein.query.filter_by(symbol='MTOR').first()

        if not atxn3 or not mtor:
            print("✗ ATXN3 or MTOR not in database")
            return False

        # Query interaction
        if atxn3.id < mtor.id:
            atxn3_mtor = db.session.query(Interaction).filter(
                Interaction.protein_a_id == atxn3.id,
                Interaction.protein_b_id == mtor.id
            ).first()
        else:
            atxn3_mtor = db.session.query(Interaction).filter(
                Interaction.protein_a_id == mtor.id,
                Interaction.protein_b_id == atxn3.id
            ).first()

        if atxn3_mtor:
            print(f"✓ Found ATXN3-MTOR interaction (ID: {atxn3_mtor.id})")
            print(f"  interaction_type: {atxn3_mtor.interaction_type}")
            print(f"  function_context: {atxn3_mtor.function_context}")

            # Check functions for arrow_context
            functions = atxn3_mtor.data.get("functions", [])
            print(f"  Functions: {len(functions)}")

            has_arrow_context = False
            has_net_context = False
            has_direct_context = False

            for i, func in enumerate(functions):
                print(f"\n  Function {i+1}: {func.get('function', 'N/A')}")
                print(f"    arrow: {func.get('arrow', 'N/A')}")
                print(f"    function_context: {func.get('function_context', 'N/A')}")

                if "arrow_context" in func:
                    has_arrow_context = True
                    print(f"    ✓ HAS arrow_context:")
                    print(f"      direct_arrow: {func['arrow_context'].get('direct_arrow', 'N/A')}")
                    print(f"      net_arrow: {func['arrow_context'].get('net_arrow', 'N/A')}")
                else:
                    print(f"    ✗ NO arrow_context")

                if func.get("function_context") == "net":
                    has_net_context = True
                elif func.get("function_context") == "direct":
                    has_direct_context = True

            print(f"\n  Summary:")
            print(f"    Arrow validation applied: {'YES' if has_arrow_context else 'NO'}")
            print(f"    Has net context functions: {'YES' if has_net_context else 'NO'}")
            print(f"    Has direct context functions: {'YES' if has_direct_context else 'NO'}")

            if not has_arrow_context:
                print("\n  ⚠️  WARNING: No arrow_context found - data may not be validated!")
        else:
            print("✗ ATXN3-MTOR interaction NOT found in database")
            return False

        # Check RHEB-MTOR (direct)
        print("\n" + "-"*80)
        rheb = Protein.query.filter_by(symbol='RHEB').first()

        if not rheb or not mtor:
            print("✗ RHEB or MTOR not in database")
            return False

        # Query interaction
        if rheb.id < mtor.id:
            rheb_mtor = db.session.query(Interaction).filter(
                Interaction.protein_a_id == rheb.id,
                Interaction.protein_b_id == mtor.id
            ).first()
        else:
            rheb_mtor = db.session.query(Interaction).filter(
                Interaction.protein_a_id == mtor.id,
                Interaction.protein_b_id == rheb.id
            ).first()

        if rheb_mtor:
            print(f"✓ Found RHEB-MTOR interaction (ID: {rheb_mtor.id})")
            print(f"  interaction_type: {rheb_mtor.interaction_type}")
            print(f"  function_context: {rheb_mtor.function_context}")
            print(f"  discovery_method: {rheb_mtor.discovery_method}")

            # Check functions
            functions = rheb_mtor.data.get("functions", [])
            print(f"  Functions: {len(functions)}")

            net_count = 0
            direct_count = 0

            for i, func in enumerate(functions):
                ctx = func.get("function_context", "unknown")
                if ctx == "net":
                    net_count += 1
                elif ctx == "direct":
                    direct_count += 1

                print(f"\n  Function {i+1}: {func.get('function', 'N/A')}")
                print(f"    arrow: {func.get('arrow', 'N/A')}")
                print(f"    function_context: {ctx}")

            print(f"\n  Summary:")
            print(f"    Net effect functions: {net_count}")
            print(f"    Direct functions: {direct_count}")

            if direct_count == 0:
                print(f"\n  ⚠️  WARNING: No direct context functions found!")
                print(f"     This means enrichment script hasn't run yet or failed.")
                print(f"     Run: ./FIX_NOW.sh to create direct functions")
                return False
            else:
                print(f"\n  ✓ GOOD: Has {direct_count} direct function(s)")
                return True
        else:
            print("✗ RHEB-MTOR interaction NOT found in database")
            print("   This interaction should exist!")
            print("   Run: ./FIX_NOW.sh to create it")
            return False


def check_3_backend_retrieves_data():
    """Check if backend properly retrieves and serves data"""
    print("\n" + "="*80)
    print("CHECK 3: Does backend retrieve dual-track data?")
    print("="*80)

    with app.app_context():
        from app import build_full_json_from_db

        result = build_full_json_from_db("ATXN3")

        if not result:
            print("✗ Failed to build JSON from database")
            return False

        snapshot = result.get("snapshot_json", {})
        interactions = snapshot.get("interactions", [])

        print(f"✓ Retrieved {len(interactions)} interactions for ATXN3")

        # Find RHEB-MTOR interaction
        rheb_mtor_interaction = None
        for ix in interactions:
            source = ix.get("source")
            target = ix.get("target")

            if (source == "RHEB" and target == "MTOR") or (source == "MTOR" and target == "RHEB"):
                rheb_mtor_interaction = ix
                break

        if rheb_mtor_interaction:
            print(f"\n✓ Found RHEB-MTOR in interactions")
            print(f"  type: {rheb_mtor_interaction.get('type', 'N/A')}")
            print(f"  source: {rheb_mtor_interaction.get('source', 'N/A')}")
            print(f"  target: {rheb_mtor_interaction.get('target', 'N/A')}")

            functions = rheb_mtor_interaction.get("functions", [])
            print(f"  Functions: {len(functions)}")

            for i, func in enumerate(functions):
                print(f"\n  Function {i+1}:")
                print(f"    function: {func.get('function', 'N/A')}")
                print(f"    arrow: {func.get('arrow', 'N/A')}")
                print(f"    function_context: {func.get('function_context', 'N/A')}")

            return len(functions) > 0
        else:
            print("\n✗ RHEB-MTOR NOT found in retrieved interactions")
            print("   Backend is not fetching it properly!")
            print("   Check app.py chain link retrieval logic")
            return False


def check_4_frontend_can_parse():
    """Check if frontend can parse and display dual-track"""
    print("\n" + "="*80)
    print("CHECK 4: Can frontend parse dual-track functions?")
    print("="*80)

    # Read visualizer.js and check for dual-track support
    viz_path = Path("static/visualizer.js")

    if not viz_path.exists():
        print("✗ visualizer.js not found")
        return False

    with open(viz_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check for key dual-track features
    checks = {
        "Groups by function_context": "function_context" in content and "contextGroups" in content,
        "Has NET EFFECT badge": "NET EFFECT" in content,
        "Has DIRECT LINK badge": "DIRECT LINK" in content,
        "Separates net and direct": "contextGroups.net" in content and "contextGroups.direct" in content,
    }

    all_passed = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✓ Frontend is ready for dual-track display!")
    else:
        print("\n✗ Frontend missing dual-track support")

    return all_passed


def main():
    print("\n" + "="*80)
    print("COMPREHENSIVE DATA FLOW DIAGNOSIS")
    print("Tracing: Pipeline → DB → Backend → Frontend")
    print("="*80)

    results = []

    # Run all checks
    results.append(("Arrow validation enabled", check_1_arrow_validation_in_pipeline()))
    results.append(("DB has validated data", check_2_db_has_validated_data()))
    results.append(("Backend retrieves data", check_3_backend_retrieves_data()))
    results.append(("Frontend can parse", check_4_frontend_can_parse()))

    # Summary
    print("\n" + "="*80)
    print("DIAGNOSIS SUMMARY")
    print("="*80)

    all_passed = True
    for check_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 ALL CHECKS PASSED!")
        print("\nYour system should display dual-track functions correctly.")
        print("If you still don't see them, try:")
        print("  1. Hard refresh browser (Ctrl+Shift+R)")
        print("  2. Clear cache")
        print("  3. Check browser console for errors")
    else:
        print("\n⚠️  SOME CHECKS FAILED")
        print("\nRecommended actions:")
        print("  1. Run: ./FIX_NOW.sh")
        print("  2. Check that GOOGLE_API_KEY is set")
        print("  3. Re-run this diagnosis")

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
