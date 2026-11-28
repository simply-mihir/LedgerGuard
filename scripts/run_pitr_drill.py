"""Run the point-in-time-recovery drill and print the result. Needs Docker and postgres:17-alpine."""

import json
from dataclasses import asdict

from ledgerguard.db.pool import close_all_pools
from ledgerguard.dr.pitr import docker_available, run_pitr_drill

if not docker_available():
    raise SystemExit("docker or postgres:17-alpine not available")
try:
    print(json.dumps(asdict(run_pitr_drill()), indent=2))
finally:
    close_all_pools()
