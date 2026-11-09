"""Exercise scheduler coordination without contacting a Docker daemon."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'qnap-live-auto-backup.sh'
FAKE = r'''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['TEST_DOCKER_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\n')
case = os.environ.get('TEST_DOCKER_CASE', '')
if args[:2] == ['compose', 'version']: sys.exit(0)
if args[0] == 'compose':
    if args[-2:] == ['config', '--quiet']: sys.exit(0)
    if 'run' in args:
        if case == 'backup-fails': sys.exit(1)
        if case != 'missing-marker': print('PASS: live central registry, test backup')
        sys.exit(0)
if args[0] == 'ps':
    if case == 'enumeration-fails': sys.exit(1)
    service = next(a.split('service=')[1] for a in args if 'service=' in a)
    print(service)
    if case == 'ambiguous': print('duplicate')
    sys.exit(0)
if args[:2] == ['container', 'inspect']: sys.exit(1)
if args[0] == 'inspect':
    print('exited' if case == 'service-stopped' else 'running')
    sys.exit(0)
if args[0] == 'stop':
    sys.exit(1 if case == 'stop-fails' and args[1] == 'live-app' else 0)
if args[0] == 'start':
    sys.exit(1 if case == 'restart-fails' and args[1] == 'live-app' else 0)
sys.exit(2)
'''


class BackupSchedulerTest(unittest.TestCase):
    def run_job(self, case='', mode='--run', locked=False):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            docker = root / 'docker'
            docker.write_text('#!' + sys.executable + '\n' + FAKE)
            docker.chmod(0o755)
            compose = root / 'compose.yml'
            compose.write_text('services: {}\n')
            log = root / 'calls.jsonl'
            if locked:
                (root / '.famquest-live-auto-backup-lock').mkdir()
            env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                   'FAMQUEST_COMPOSE_FILE': str(compose),
                   'FAMQUEST_BACKUP_LOCK_ROOT': str(root),
                   'TEST_DOCKER_LOG': str(log), 'TEST_DOCKER_CASE': case}
            result = subprocess.run(['sh', str(SCRIPT), mode], env=env,
                                    capture_output=True, text=True)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            lock_exists = (root / '.famquest-live-auto-backup-lock').exists()
            return result, calls, lock_exists

    def test_check_never_stops_or_runs_services(self):
        result, calls, locked = self.run_job(mode='--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(c[0] in ('stop', 'start') or 'run' in c for c in calls))
        self.assertFalse(locked)

    def test_backup_quiesces_writers_and_resumes_in_order(self):
        result, calls, locked = self.run_job()
        self.assertEqual(result.returncode, 0, result.stderr)
        changes = [c for c in calls if c[0] in ('stop', 'start') or 'run' in c]
        self.assertEqual(changes[0:2], [['stop', 'live-mcp'], ['stop', 'live-app']])
        self.assertIn('--no-deps', changes[2])
        self.assertIn('--rm', changes[2])
        self.assertEqual(changes[-2:], [['start', 'live-app'], ['start', 'live-mcp']])
        self.assertFalse(locked)

    def test_failures_do_not_claim_success_and_restore_writers(self):
        for case in ('backup-fails', 'missing-marker', 'stop-fails', 'restart-fails'):
            with self.subTest(case=case):
                result, calls, locked = self.run_job(case)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(['start', 'live-app'], calls)
                self.assertIn(['start', 'live-mcp'], calls)
                self.assertFalse(locked)

    def test_failed_preconditions_never_stop_services(self):
        for case in ('enumeration-fails', 'ambiguous', 'service-stopped'):
            with self.subTest(case=case):
                result, calls, locked = self.run_job(case)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(c[0] in ('stop', 'start') for c in calls))
                self.assertFalse(locked)

    def test_existing_lock_is_preserved(self):
        result, calls, locked = self.run_job(locked=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] in ('stop', 'start') for c in calls))
        self.assertTrue(locked)


if __name__ == '__main__':
    unittest.main()
