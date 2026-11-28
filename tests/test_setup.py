"""Automated tests for the TaskFlow AI setup script."""

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, call
import runpy

import setup


class TestSetup(unittest.TestCase):

    def setUp(self):
        """Create an isolated installation directory for each test."""
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name)
        self.venv = self.root / ".venv"
        self.venv_python = self.venv / "python"

        self.backend = self.root / "backend"
        self.backend.mkdir()

        self.env_file = self.backend / ".env"
        self.env_template = self.backend / ".env.example"

        self.env_template.write_text(
            "GEMINI_API_KEY=\n",
            encoding="utf-8",
        )

        # Redirect setup paths to the temporary directory.
        patches = {
            "ROOT": self.root,
            "VENV": self.venv,
            "VENV_PYTHON": self.venv_python,
            "ENV_FILE": self.env_file,
            "ENV_TEMPLATE": self.env_template,
        }

        for name, value in patches.items():
            patcher = patch.object(setup, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        # Simulate subprocess commands without executing them.
        subprocess_patcher = patch("setup.subprocess.run")
        self.mock_run = subprocess_patcher.start()
        self.addCleanup(subprocess_patcher.stop)

        # Simulate a supported Python version.
        version_patcher = patch(
            "setup.sys.version_info",
            (3, 12, 0),
        )
        version_patcher.start()
        self.addCleanup(version_patcher.stop)

    def test_creates_virtual_environment(self):
        """Setup creates a virtual environment when missing."""
        setup.setup()

        self.mock_run.assert_any_call(
            [setup.sys.executable, "-m", "venv", str(self.venv)],
            check=True,
            cwd=self.root,
            shell=False
        )

    def test_reuses_existing_virtual_environment(self):
        """Setup does not recreate an existing virtual environment."""
        self.venv.mkdir()
        self.venv_python.touch()

        setup.setup()

        create_command = call(
            [setup.sys.executable, "-m", "venv", str(self.venv)],
            check=True,
            cwd=self.root,
            shell=False
        )

        self.assertNotIn(
            create_command,
            self.mock_run.call_args_list,
        )

    def test_installs_dependencies(self):
        """Setup installs dependencies using the virtual environment."""
        setup.setup()

        self.mock_run.assert_any_call(
            [
                str(self.venv_python),
                "-m",
                "pip",
                "install",
                "-r",
                "requirements.txt",
            ],
            check=True,
            cwd=self.root,
            shell=False
        )

    def test_initializes_database(self):
        """Setup executes the database initialization module."""
        setup.setup()

        self.mock_run.assert_any_call(
            [str(self.venv_python), "-m", "backend.init_db"],
            check=True,
            cwd=self.root,
            shell=False
        )

    def test_skips_seed_by_default(self):
        """Sample data is not loaded by default."""
        setup.setup()

        seed_command = call(
            [str(self.venv_python), "-m", "backend.seed_db"],
            check=True,
            cwd=self.root,
            shell=False
        )

        self.assertNotIn(
            seed_command,
            self.mock_run.call_args_list,
        )

    def test_loads_sample_data_when_requested(self):
        """Setup loads sample data when seeding is enabled."""
        setup.setup(seed=True)

        self.mock_run.assert_any_call(
            [str(self.venv_python), "-m", "backend.seed_db"],
            check=True,
            cwd=self.root,
            shell=False
        )

    def test_creates_environment_file(self):
        """Setup creates .env from the configuration template."""
        setup.setup()

        self.assertTrue(self.env_file.exists())
        self.assertEqual(
            self.env_file.read_text(encoding="utf-8"),
            self.env_template.read_text(encoding="utf-8"),
        )

    def test_preserves_existing_environment_file(self):
        """Setup does not overwrite existing configuration."""
        existing_content = "GEMINI_API_KEY=test-placeholder\n"

        self.env_file.write_text(
            existing_content,
            encoding="utf-8",
        )

        setup.setup()

        self.assertEqual(
            self.env_file.read_text(encoding="utf-8"),
            existing_content,
        )

    def test_accepts_supported_python_version(self):
        """Python 3.12 passes version validation."""
        setup.check_python_version()

    def test_rejects_unsupported_python_version(self):
        """Unsupported Python versions stop installation."""
        with patch("setup.sys.version_info", (3, 11, 0)):
            with self.assertRaises(RuntimeError):
                setup.setup()

        self.mock_run.assert_not_called()
        self.assertFalse(self.env_file.exists())

    def test_stops_when_command_fails(self):
        """A failed installation command stops further execution."""
        self.mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd="installation command",
        )

        with self.assertRaises(subprocess.CalledProcessError):
            setup.setup()

        self.assertEqual(self.mock_run.call_count, 1)
        self.assertFalse(self.env_file.exists())

    def test_installation_command_order(self):
        """Installation commands execute in the correct order."""
        setup.setup(seed=True)

        expected_calls = [
            call(
                [setup.sys.executable, "-m", "venv", str(self.venv)],
                check=True,
                cwd=self.root,
                shell=False
            ),
            call(
                [
                    str(self.venv_python),
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    "requirements.txt",
                ],
                check=True,
                cwd=self.root,
                shell=False
            ),
            call(
                [str(self.venv_python), "-m", "backend.init_db"],
                check=True,
                cwd=self.root,
                shell=False
            ),
            call(
                [str(self.venv_python), "-m", "backend.seed_db"],
                check=True,
                cwd=self.root,
                shell=False
            ),
        ]

        self.assertEqual(
            self.mock_run.call_args_list,
            expected_calls,
        )

    def test_commands_do_not_use_shell(self):
        """Installation commands execute without shell access."""
        setup.setup(seed=True)

        self.assertEqual(self.mock_run.call_count, 4)

        for command in self.mock_run.call_args_list:
            self.assertIs(command.kwargs["shell"], False)
            self.assertIs(command.kwargs["check"], True)
            self.assertIsInstance(command.args[0], list)

    def test_stops_when_dependency_installation_fails(self):
        """Dependency failure prevents database initialization."""
        self.mock_run.side_effect = [
            None,
            subprocess.CalledProcessError(
                returncode=1,
                cmd="pip install",
            ),
        ]

        with self.assertRaises(subprocess.CalledProcessError):
            setup.setup(seed=True)

        self.assertEqual(self.mock_run.call_count, 2)
        self.assertFalse(self.env_file.exists())

    def test_stops_when_database_initialization_fails(self):
        """Database failure prevents sample data loading."""
        self.mock_run.side_effect = [
            None,
            None,
            subprocess.CalledProcessError(
                returncode=1,
                cmd="backend.init_db",
            ),
        ]

        with self.assertRaises(subprocess.CalledProcessError):
            setup.setup(seed=True)

        self.assertEqual(self.mock_run.call_count, 3)
        self.assertFalse(self.env_file.exists())

    def test_stops_when_sample_data_loading_fails(self):
        """Failed seeding does not report successful installation."""
        self.mock_run.side_effect = [
            None,
            None,
            None,
            subprocess.CalledProcessError(
                returncode=1,
                cmd="backend.seed_db",
            ),
        ]

        with self.assertRaises(subprocess.CalledProcessError):
            setup.setup(seed=True)

        self.assertEqual(self.mock_run.call_count, 4)
        self.assertFalse(self.env_file.exists())

    def test_missing_environment_template(self):
        """A missing configuration template raises an error."""
        self.env_template.unlink()

        with self.assertRaises(FileNotFoundError):
            setup.setup()

        self.assertFalse(self.env_file.exists())

    def test_existing_configuration_without_template(self):
        """Existing configuration is preserved without a template."""
        self.env_template.unlink()

        existing_content = "GEMINI_API_KEY=test-placeholder\n"

        self.env_file.write_text(
            existing_content,
            encoding="utf-8",
        )

        setup.setup()

        self.assertEqual(
            self.env_file.read_text(encoding="utf-8"),
            existing_content,
        )


class TestGetVenvPython(unittest.TestCase):

    def test_windows_python_path(self):
        """Windows uses the Scripts directory."""
        venv = Path(".venv")

        self.assertEqual(
            setup.get_venv_python(venv, "nt"),
            venv / "Scripts" / "python.exe",
        )

    def test_posix_python_path(self):
        """Linux and macOS use the bin directory."""
        venv = Path(".venv")

        self.assertEqual(
            setup.get_venv_python(venv, "posix"),
            venv / "bin" / "python",
        )


class TestMain(unittest.TestCase):

    @patch("setup.setup")
    def test_default_installation(self, mock_setup):
        """Default installation does not load sample data."""
        self.assertEqual(setup.main([]), 0)

        mock_setup.assert_called_once_with(seed=False)

    @patch("setup.setup")
    def test_seed_installation(self, mock_setup):
        """The seed argument enables sample data."""
        self.assertEqual(setup.main(["--seed"]), 0)

        mock_setup.assert_called_once_with(seed=True)

    @patch("builtins.print")
    @patch("setup.setup")
    def test_command_failure(self, mock_setup, mock_print):
        """Failed subprocess commands return exit code one."""
        mock_setup.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd="installation command",
        )

        self.assertEqual(setup.main([]), 1)

        mock_print.assert_called_once_with(
            "Setup failed. Review the error above."
        )

    @patch("builtins.print")
    @patch("setup.setup")
    def test_runtime_error(self, mock_setup, mock_print):
        """Runtime errors return exit code one."""
        mock_setup.side_effect = RuntimeError(
            "Unsupported Python version."
        )

        self.assertEqual(setup.main([]), 1)

        mock_print.assert_called_once_with(
            "Setup failed: Unsupported Python version."
        )

    @patch("builtins.print")
    @patch("setup.setup")
    def test_os_error(self, mock_setup, mock_print):
        """Operating system errors return exit code one."""
        mock_setup.side_effect = OSError(
            "Permission denied."
        )

        self.assertEqual(setup.main([]), 1)

        mock_print.assert_called_once_with(
            "Setup failed: Permission denied."
        )

    @patch("setup.setup")
    def test_invalid_argument(self, mock_setup):
        """Unrecognized arguments prevent installation."""
        with self.assertRaises(SystemExit) as context:
            setup.main(["--invalid"])

        self.assertEqual(context.exception.code, 2)
        mock_setup.assert_not_called()

    @patch("subprocess.run")
    @patch("sys.version_info", (3, 11, 0))
    @patch("builtins.print")
    def test_script_entry_point(
        self, mock_print, mock_run
    ):
        """Direct execution exits with the installation result."""
        with patch(
            "sys.argv",
            [str(setup.ROOT / "setup.py")],
        ):
            with self.assertRaises(SystemExit) as context:
                runpy.run_path(
                    str(setup.ROOT / "setup.py"),
                    run_name="__main__",
                )

        self.assertEqual(context.exception.code, 1)
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()