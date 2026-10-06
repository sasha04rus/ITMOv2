import sys
import subprocess
from pathlib import Path
import unittest


class TestPersistence(unittest.TestCase):
    def test_subscriptions_do_not_persist_across_process_restart(self):
        # Run two separate Python processes to prove lack of persistence.
        # First process: add a subscriber and print len(subscribers) => expects 1
        # Second process: fresh interpreter, print len(subscribers) => expects 0
        demo_dir = Path(__file__).parent
        py = sys.executable

        code_add = (
            "import service; "
            "service.subscribe('Ann'); "
            "print(len(service.subscribers))"
        )
        code_check = (
            "import service; "
            "print(len(service.subscribers))"
        )

        r1 = subprocess.run(
            [py, "-c", code_add],
            cwd=str(demo_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(r1.stdout.strip(), "1")

        r2 = subprocess.run(
            [py, "-c", code_check],
            cwd=str(demo_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(r2.stdout.strip(), "0")


if __name__ == "__main__":
    unittest.main()
