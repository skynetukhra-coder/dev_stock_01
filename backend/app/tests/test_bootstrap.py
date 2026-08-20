import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from app.main import health_payload


class BootstrapTests(unittest.TestCase):
    def test_health_payload(self) -> None:
        self.assertEqual(health_payload()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
