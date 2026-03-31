from __future__ import annotations

import argparse

from app.db.session import bootstrap_database, get_session_factory
from app.services.data_lifecycle import purge_soft_deleted_claims, reset_demo_data, soft_delete_claim
from app.services.seed import seed_demo_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ClaimMate AI data lifecycle utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("seed-demo", help="Seed demo merchants and claims when they are missing")
    subparsers.add_parser("reset-demo", help="Delete only demo merchants and reseed them")

    delete_parser = subparsers.add_parser("soft-delete-claim", help="Soft delete a claim with retention metadata")
    delete_parser.add_argument("--claim-id", type=int, required=True)
    delete_parser.add_argument("--actor", default="ops_script")
    delete_parser.add_argument("--reason", required=True)
    delete_parser.add_argument("--retain-days", type=int, default=None)

    purge_parser = subparsers.add_parser("purge-soft-deleted", help="Hard delete claims past their retention date")
    purge_parser.add_argument("--dry-run", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    bootstrap_database()
    session_factory = get_session_factory()
    session = session_factory()
    try:
        if args.command == "seed-demo":
            seed_demo_data(session)
            print("Demo data seed completed.")
            return

        if args.command == "reset-demo":
            result = reset_demo_data(session)
            print(result)
            return

        if args.command == "soft-delete-claim":
            claim = soft_delete_claim(
                session,
                args.claim_id,
                actor=args.actor,
                reason=args.reason,
                retain_days=args.retain_days,
            )
            print(
                {
                    "claim_id": claim.id,
                    "deleted_at": claim.deleted_at.isoformat() if claim.deleted_at else None,
                    "retention_until": claim.retention_until.isoformat() if claim.retention_until else None,
                }
            )
            return

        if args.command == "purge-soft-deleted":
            if args.dry_run:
                print("Dry-run mode is not implemented. Run without --dry-run to purge eligible claims.")
                return
            purged = purge_soft_deleted_claims(session)
            print({"purged_claims": purged})
            return
    finally:
        session.close()


if __name__ == "__main__":
    main()
