"""Phase 2 contract scaffold. No live sync is advertised until transport is implemented.

The database already contains resumable cursors, master/exception identity, etags,
conflict snapshots and tombstones. The pure resolver below fixes winner semantics.
See docs/INTEGRATIONS.md for the ordered implementation and verification contract.
"""


def resolve(local, remote):
    """Compare content timestamps, never a bookkeeping sync timestamp; Google wins ties."""
    return "google" if remote["updated_at"] >= local["updated_at"] else "local"


class GoogleCalendarTransport:
    def sync(self):
        return {
            "status": "not_implemented",
            "message": "Use local Calendar. OAuth, incremental pull, push and channel renewal are Phase 2 work.",
        }
