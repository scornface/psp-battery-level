"""Pure publication and real sampler integration remain separate contracts."""
from pathlib import Path
import unittest
from support import ROOT, TESTS, C_TESTS, temporary_directory, compile_program, run_program


class HomePowerTests(unittest.TestCase):
    def test_staging_and_publication(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "frames"
            compile_program(binary, C_TESTS / "home_power_frames.c", ROOT / "src/home/sprite.c",
                            includes=[ROOT / "src/home"])
            run_program(binary)

    def test_sampler_service_order_and_invalidity(self):
        with temporary_directory() as directory:
            binary = Path(directory) / "worker"
            compile_program(binary, C_TESTS / "home_power_worker.c", ROOT / "src/home/power_worker.c",
                            ROOT / "src/home/sprite.c", includes=[TESTS / "stubs", ROOT / "src/home"],
                            defines=["HOME_POWER_HOST_TEST"])
            run_program(binary)
