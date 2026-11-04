import { execFileSync } from 'node:child_process';
import path from 'node:path';

export interface SyntheticOperator {
  username: string;
  email: string;
  password: string;
  operatorId: string;
  totpSecret?: string;
}

const PROJECT_ROOT = path.resolve(__dirname, '../../..');

/**
 * Dynamically provision an isolated synthetic operator for real browser testing.
 * Credentials are generated at runtime and never persisted to version control.
 */
export function provisionSyntheticOperator(options: { enableTotp?: boolean } = {}): SyntheticOperator {
  const script = `
import json, uuid, time
from ledgerguard.auth.models import CreateOperatorRequest
from ledgerguard.auth.service import create_operator_account, enroll_totp
from ledgerguard.db.pool import get_db_connection
from ledgerguard.config import settings

uid = uuid.uuid4().hex[:10]
username = f"e2e_{uid}"
email = f"{username}@test.internal"
password = f"Sec!{uuid.uuid4().hex[:12]}A1"

enable_totp = ${options.enableTotp ? 'True' : 'False'}
req = CreateOperatorRequest(
    username=username,
    email=email,
    password=password,
    role="ADMIN",
    enable_totp=enable_totp,
)
op = create_operator_account(req)

totp_secret = None
if enable_totp:
    secret, _, _ = enroll_totp(op.operator_id)
    # Set totp_secret directly with last_totp_step in the past so the current step's code is fresh
    current_step = int(time.time() // 30)
    with get_db_connection(settings.coordinator_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE operators
                SET totp_secret = %s,
                    totp_enabled = TRUE,
                    pending_totp_secret = NULL,
                    pending_totp_expires_at = NULL,
                    last_totp_step = %s,
                    updated_at = NOW()
                WHERE operator_id = %s
            """, (secret, current_step - 2, op.operator_id))
            conn.commit()
    totp_secret = secret

print(json.dumps({
    "username": username,
    "email": email,
    "password": password,
    "operatorId": str(op.operator_id),
    "totpSecret": totp_secret,
}))
`;

  const output = execFileSync('uv', ['run', 'python', '-c', script], {
    cwd: PROJECT_ROOT,
    encoding: 'utf-8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  return JSON.parse(output.trim());
}

/**
 * Compute the active RFC 6238 TOTP verification code for an authenticator secret.
 */
export function getTotpCode(secret: string): string {
  const script = `
import sys
from ledgerguard.auth.totp import get_totp_code
print(get_totp_code(sys.argv[1]))
`;

  const output = execFileSync('uv', ['run', 'python', '-c', script, secret], {
    cwd: PROJECT_ROOT,
    encoding: 'utf-8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  return output.trim();
}
