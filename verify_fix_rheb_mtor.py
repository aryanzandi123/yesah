#!/usr/bin/env python3
"""
Script to verify and fix RHEB-MTOR interaction in database.

This ensures:
1. RHEB-MTOR interaction exists
2. It has interaction_type='direct'
3. It has function_context='direct'
4. It has proper arrow and direction
"""
import os
import sys
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

from app import app
from models import db, Protein, Interaction

def main():
    with app.app_context():
        print("="*80)
        print("VERIFY AND FIX RHEB-MTOR INTERACTION")
        print("="*80)

        # Check if RHEB and MTOR proteins exist
        rheb = Protein.query.filter_by(symbol='RHEB').first()
        mtor = Protein.query.filter_by(symbol='MTOR').first()

        if not rheb:
            print("ERROR: RHEB protein not found in database!")
            return

        if not mtor:
            print("ERROR: MTOR protein not found in database!")
            return

        print(f"\n✓ RHEB found (ID: {rheb.id})")
        print(f"✓ MTOR found (ID: {mtor.id})")

        # Query for RHEB-MTOR interaction (respecting canonical ordering)
        if rheb.id < mtor.id:
            interaction = db.session.query(Interaction).filter(
                Interaction.protein_a_id == rheb.id,
                Interaction.protein_b_id == mtor.id
            ).first()
        else:
            interaction = db.session.query(Interaction).filter(
                Interaction.protein_a_id == mtor.id,
                Interaction.protein_b_id == rheb.id
            ).first()

        if not interaction:
            print("\n✗ ERROR: RHEB-MTOR interaction NOT FOUND in database!")
            print("\nThis is the root cause of the issue. The validate_existing_arrows.py script")
            print("should have created this interaction, but it doesn't exist.")
            print("\nRecommendation: Re-run validate_existing_arrows.py script WITHOUT --dry-run")
            return

        print(f"\n✓ RHEB-MTOR interaction found (ID: {interaction.id})")
        print("\nCurrent properties:")
        print(f"  protein_a: {interaction.protein_a.symbol} (ID: {interaction.protein_a_id})")
        print(f"  protein_b: {interaction.protein_b.symbol} (ID: {interaction.protein_b_id})")
        print(f"  interaction_type: {interaction.interaction_type}")
        print(f"  discovered_in_query: {interaction.discovered_in_query}")
        print(f"  discovery_method: {interaction.discovery_method}")
        print(f"  arrow: {interaction.arrow}")
        print(f"  direction: {interaction.direction}")
        print(f"  function_context: {interaction.function_context}")
        print(f"  upstream_interactor: {interaction.upstream_interactor}")
        print(f"  mediator_chain: {interaction.mediator_chain}")

        # Check function data
        if 'functions' in interaction.data:
            print(f"\n  Functions ({len(interaction.data['functions'])}):")
            for idx, func in enumerate(interaction.data['functions']):
                print(f"    {idx+1}. {func.get('function', 'N/A')}")
                print(f"       arrow: {func.get('arrow', 'N/A')}")
                print(f"       direct_arrow: {func.get('direct_arrow', 'N/A')}")
                print(f"       net_arrow: {func.get('net_arrow', 'N/A')}")
                print(f"       function_context: {func.get('function_context', 'N/A')}")

        # Verify and fix issues
        needs_fix = False
        issues = []

        if interaction.interaction_type != 'direct':
            issues.append(f"interaction_type is '{interaction.interaction_type}', should be 'direct'")
            needs_fix = True

        if interaction.function_context != 'direct':
            issues.append(f"function_context is '{interaction.function_context}', should be 'direct'")
            needs_fix = True

        if interaction.upstream_interactor is not None:
            issues.append(f"upstream_interactor is '{interaction.upstream_interactor}', should be None for direct")
            needs_fix = True

        if interaction.mediator_chain:
            issues.append(f"mediator_chain is {interaction.mediator_chain}, should be None/[] for direct")
            needs_fix = True

        if not interaction.arrow:
            issues.append(f"arrow is empty, should be 'activates' for RHEB→MTOR")
            needs_fix = True

        if issues:
            print("\n" + "="*80)
            print("ISSUES FOUND:")
            print("="*80)
            for issue in issues:
                print(f"  ✗ {issue}")

            print("\n" + "="*80)
            print("FIXING ISSUES...")
            print("="*80)

            # Fix interaction_type
            if interaction.interaction_type != 'direct':
                print("  → Setting interaction_type = 'direct'")
                interaction.interaction_type = 'direct'
                interaction.data['interaction_type'] = 'direct'

            # Fix function_context
            if interaction.function_context != 'direct':
                print("  → Setting function_context = 'direct'")
                interaction.function_context = 'direct'
                interaction.data['function_context'] = 'direct'

            # Fix upstream_interactor
            if interaction.upstream_interactor is not None:
                print("  → Setting upstream_interactor = None")
                interaction.upstream_interactor = None
                if 'upstream_interactor' in interaction.data:
                    del interaction.data['upstream_interactor']

            # Fix mediator_chain
            if interaction.mediator_chain:
                print("  → Setting mediator_chain = None")
                interaction.mediator_chain = None
                if 'mediator_chain' in interaction.data:
                    del interaction.data['mediator_chain']

            # Fix arrow if empty
            if not interaction.arrow:
                print("  → Setting arrow = 'activates' (RHEB activates MTOR)")
                interaction.arrow = 'activates'
                interaction.data['arrow'] = 'activates'

            # Fix direction if needed
            if not interaction.direction or interaction.direction == 'unknown':
                # Determine direction based on canonical ordering
                # RHEB → MTOR means protein_a (smaller ID) → protein_b (larger ID)
                if rheb.id < mtor.id:
                    # RHEB is protein_a, MTOR is protein_b
                    # RHEB→MTOR means a_to_b
                    print("  → Setting direction = 'a_to_b' (RHEB→MTOR)")
                    interaction.direction = 'a_to_b'
                    interaction.data['direction'] = 'a_to_b'
                else:
                    # MTOR is protein_a, RHEB is protein_b
                    # RHEB→MTOR means b_to_a
                    print("  → Setting direction = 'b_to_a' (RHEB→MTOR)")
                    interaction.direction = 'b_to_a'
                    interaction.data['direction'] = 'b_to_a'

            # Update timestamp
            interaction.updated_at = datetime.utcnow()

            # Commit changes
            try:
                db.session.commit()
                print("\n✓ Changes committed to database successfully!")
            except Exception as e:
                db.session.rollback()
                print(f"\n✗ ERROR committing changes: {e}")
                return

            print("\n" + "="*80)
            print("VERIFICATION AFTER FIX:")
            print("="*80)
            print(f"  interaction_type: {interaction.interaction_type}")
            print(f"  function_context: {interaction.function_context}")
            print(f"  arrow: {interaction.arrow}")
            print(f"  direction: {interaction.direction}")
            print(f"  upstream_interactor: {interaction.upstream_interactor}")
            print(f"  mediator_chain: {interaction.mediator_chain}")

        else:
            print("\n" + "="*80)
            print("✓ NO ISSUES FOUND - RHEB-MTOR interaction is correctly configured!")
            print("="*80)

        print("\n" + "="*80)
        print("DONE")
        print("="*80)

if __name__ == "__main__":
    main()
