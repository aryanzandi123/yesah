#!/usr/bin/env python3
"""
Script to check database for RHEB-MTOR interaction and ATXN3 interactions.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app import app
from models import db, Protein, Interaction

def main():
    with app.app_context():
        # Check RHEB-MTOR interaction
        rheb = Protein.query.filter_by(symbol='RHEB').first()
        mtor = Protein.query.filter_by(symbol='MTOR').first()

        if rheb and mtor:
            print(f"RHEB ID: {rheb.id}, MTOR ID: {mtor.id}")

            # Query for interaction
            interaction = db.session.query(Interaction).filter(
                ((Interaction.protein_a_id == rheb.id) & (Interaction.protein_b_id == mtor.id)) |
                ((Interaction.protein_a_id == mtor.id) & (Interaction.protein_b_id == rheb.id))
            ).first()

            if interaction:
                print(f"\nFound RHEB-MTOR interaction (ID: {interaction.id})")
                print(f"  protein_a: {interaction.protein_a.symbol} (ID: {interaction.protein_a_id})")
                print(f"  protein_b: {interaction.protein_b.symbol} (ID: {interaction.protein_b_id})")
                print(f"  interaction_type: {interaction.interaction_type}")
                print(f"  discovered_in_query: {interaction.discovered_in_query}")
                print(f"  arrow: {interaction.arrow}")
                print(f"  direction: {interaction.direction}")
                print(f"  upstream_interactor: {interaction.upstream_interactor}")
                print(f"  mediator_chain: {interaction.mediator_chain}")
                print(f"  function_context: {interaction.function_context}")

                # Check functions
                if 'functions' in interaction.data:
                    print(f"\n  Functions ({len(interaction.data['functions'])}):")
                    for func in interaction.data['functions']:
                        print(f"    - {func.get('function', 'N/A')}")
                        print(f"      arrow: {func.get('arrow', 'N/A')}")
                        print(f"      direct_arrow: {func.get('direct_arrow', 'N/A')}")
                        print(f"      net_arrow: {func.get('net_arrow', 'N/A')}")
                        print(f"      function_context: {func.get('function_context', 'N/A')}")
            else:
                print("\nNo RHEB-MTOR interaction found in database")
        else:
            print(f"RHEB: {rheb}, MTOR: {mtor}")

        # Also check ATXN3 interactions
        print("\n" + "="*60)
        atxn3 = Protein.query.filter_by(symbol='ATXN3').first()
        if atxn3:
            interactions = db.session.query(Interaction).filter(
                (Interaction.protein_a_id == atxn3.id) |
                (Interaction.protein_b_id == atxn3.id)
            ).all()

            print(f"\nATXN3 has {len(interactions)} total interactions")

            # Look for indirect interactions
            indirect = [i for i in interactions if i.interaction_type == 'indirect']
            direct = [i for i in interactions if i.interaction_type == 'direct']
            print(f"  {len(direct)} direct interactions")
            print(f"  {len(indirect)} indirect interactions")

            # Check if any involve MTOR or RHEB
            for i in interactions:
                partner_id = i.protein_b_id if i.protein_a_id == atxn3.id else i.protein_a_id
                partner = db.session.get(Protein, partner_id)
                if partner and partner.symbol in ['MTOR', 'RHEB']:
                    print(f"\n  ATXN3-{partner.symbol} interaction (ID: {i.id}):")
                    print(f"    interaction_type: {i.interaction_type}")
                    print(f"    discovered_in_query: {i.discovered_in_query}")
                    print(f"    upstream_interactor: {i.upstream_interactor}")
                    print(f"    mediator_chain: {i.mediator_chain}")
                    print(f"    function_context: {i.function_context}")

if __name__ == "__main__":
    main()
