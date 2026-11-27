"""Automated tests for the TaskFlow AI application launcher."""

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch, call
from http.client import HTTPException
import runpy

import run


class TestWaitForService(unittest.TestCase):

    def setUp(self):
        self.process = MagicMock()
        self.process.poll.return_value = None
        self.url = "http://127.0.0.1:8000/health"

        patcher = patch("run.HTTPConnection")
        self.mock_connection = patcher.start()
        self.addCleanup(patcher.stop)

        self.connection = self.mock_connection.return_value
        self.connection.getresponse.return_value.status = 200

    def test_service_ready(self):
        """A successful HTTP response indicates readiness."""
        run.wait_for_service(self.url, self.process)

        self.mock_connection.assert_called_once_with(
            "127.0.0.1", 8000, timeout=1
        )

        self.connection.request.assert_called_once_with(
            "GET", "/health"
        )

        self.connection.close.assert_called_once()

    def test_frontend_health_endpoint(self):
        """Frontend health checks use the correct port and path."""
        run.wait_for_service(
            f"{run.FRONTEND_URL}/_stcore/health",
            self.process,
        )

        self.mock_connection.assert_called_once_with(
            "127.0.0.1", 8501, timeout=1
        )

        self.connection.request.assert_called_once_with(
            "GET", "/_stcore/health"
        )

    @patch("run.time.sleep")
    def test_retries_until_service_ready(self, mock_sleep):
        """Temporary connection failures are retried."""
        self.connection.request.side_effect = [
            ConnectionRefusedError("Connection refused"),
            None,
        ]

        run.wait_for_service(self.url, self.process)

        self.assertEqual(
            self.connection.request.call_count, 2
        )
        self.assertEqual(
            self.connection.close.call_count, 2
        )
        mock_sleep.assert_called_once_with(0.5)

    @patch("run.time.sleep")
    def test_retries_http_exception(self, mock_sleep):
        """HTTP protocol errors are retried safely."""
        available = MagicMock(status=200)

        self.connection.getresponse.side_effect = [
            HTTPException("Invalid HTTP response"),
            available,
        ]

        run.wait_for_service(self.url, self.process)

        self.assertEqual(
            self.connection.getresponse.call_count, 2
        )
        self.assertEqual(
            self.connection.close.call_count, 2
        )
        mock_sleep.assert_called_once_with(0.5)

    def test_process_exits_during_startup(self):
        """Startup fails if the service process exits."""
        self.process.poll.return_value = 1

        with self.assertRaisesRegex(
            RuntimeError, "Service exited during startup"
        ):
            run.wait_for_service(self.url, self.process)

        self.mock_connection.assert_not_called()

    @patch("run.time.sleep")
    @patch("run.time.monotonic")
    def test_service_startup_timeout(
        self, mock_time, mock_sleep
    ):
        """Startup fails when the service never becomes ready."""
        mock_time.side_effect = [0, 0, 31]

        self.connection.request.side_effect = (
            ConnectionRefusedError("Connection refused")
        )

        with self.assertRaisesRegex(
            RuntimeError, "Service did not become ready"
        ):
            run.wait_for_service(
                self.url, self.process, timeout=30
            )

        self.connection.close.assert_called_once()

    def test_rejects_external_url(self):
        """Health checks cannot access external websites."""
        with self.assertRaisesRegex(
            ValueError, "Unauthorized health-check URL"
        ):
            run.wait_for_service(
                "https://example.com",
                self.process,
            )

        self.mock_connection.assert_not_called()

    def test_rejects_file_url(self):
        """Health checks cannot access local files."""
        with self.assertRaisesRegex(
            ValueError, "Unauthorized health-check URL"
        ):
            run.wait_for_service(
                "file:///example.txt",
                self.process,
            )

        self.mock_connection.assert_not_called()

    def test_rejects_unapproved_local_endpoint(self):
        """Only approved localhost endpoints are accepted."""
        with self.assertRaisesRegex(
            ValueError, "Unauthorized health-check URL"
        ):
            run.wait_for_service(
                "http://127.0.0.1:8000/employees",
                self.process,
            )

        self.mock_connection.assert_not_called()

    @patch("run.time.sleep")
    def test_retries_non_successful_response(self, mock_sleep):
        """A non-200 response does not indicate readiness."""
        self.connection.getresponse.side_effect = [
            MagicMock(status=503),
            MagicMock(status=200),
        ]

        run.wait_for_service(self.url, self.process)

        self.assertEqual(
            self.connection.getresponse.call_count, 2
        )
        mock_sleep.assert_called_once_with(0.5)

    @patch("run.time.sleep")
    def test_does_not_follow_redirects(self, mock_sleep):
        """Redirect responses do not trigger external requests."""
        redirect = MagicMock(status=302)
        redirect.getheader.return_value = "https://example.com"

        self.connection.getresponse.side_effect = [
            redirect,
            MagicMock(status=200),
        ]

        run.wait_for_service(self.url, self.process)

        self.assertEqual(
            self.mock_connection.call_args_list,
            [
                call("127.0.0.1", 8000, timeout=1),
                call("127.0.0.1", 8000, timeout=1),
            ],
        )

        self.assertEqual(
            self.connection.request.call_args_list,
            [
                call("GET", "/health"),
                call("GET", "/health"),
            ],
        )

        redirect.getheader.assert_not_called()
        mock_sleep.assert_called_once_with(0.5)


class TestStopService(unittest.TestCase):

    def test_stops_running_process(self):
        """A running process is terminated and awaited."""
        process = MagicMock()
        process.poll.return_value = None

        run.stop_service(process)

        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)
        process.kill.assert_not_called()

    def test_ignores_stopped_process(self):
        """An exited process does not need termination."""
        process = MagicMock()
        process.poll.return_value = 0

        run.stop_service(process)

        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_handles_missing_process(self):
        """Cleanup accepts a process that was never started."""
        run.stop_service(None)

    def test_kills_unresponsive_process(self):
        """An unresponsive process is forcibly stopped."""
        process = MagicMock()
        process.poll.return_value = None

        process.wait.side_effect = [
            subprocess.TimeoutExpired("service", 5),
            0,
        ]

        run.stop_service(process)

        process.terminate.assert_called_once()
        process.kill.assert_called_once()

        self.assertEqual(
            process.wait.call_args_list,
            [call(timeout=5), call()],
        )


class TestRun(unittest.TestCase):

    def setUp(self):
        """Create an isolated launcher environment."""
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name)
        self.python = self.root / "python"
        self.database = self.root / "taskflow.db"

        self.python.touch()
        self.database.touch()

        self.backend = MagicMock()
        self.frontend = MagicMock()

        self.backend.poll.return_value = None
        self.frontend.poll.return_value = None

        patches = {
            "ROOT": self.root,
            "VENV_PYTHON": self.python,
            "DATABASE": self.database,
        }

        for name, value in patches.items():
            patcher = patch.object(run, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.mock_popen = self.start_patch(
            "run.subprocess.Popen"
        )
        self.mock_popen.side_effect = [
            self.backend,
            self.frontend,
        ]

        self.mock_health = self.start_patch(
            "run.wait_for_service"
        )

        self.mock_browser = self.start_patch(
            "run.webbrowser.open"
        )
        self.mock_browser.return_value = True

        self.mock_sleep = self.start_patch(
            "run.time.sleep"
        )

        # Simulate Ctrl+C to exit the monitoring loop.
        self.mock_sleep.side_effect = KeyboardInterrupt

    def start_patch(self, target):
        """Start a mock and register automatic cleanup."""
        patcher = patch(target)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def test_missing_virtual_environment(self):
        """Startup fails if setup has not created a venv."""
        self.python.unlink()

        with self.assertRaisesRegex(
            RuntimeError, "Run python setup.py first"
        ):
            run.run()

        self.mock_popen.assert_not_called()

    def test_missing_database(self):
        """Startup fails if the database is missing."""
        self.database.unlink()

        with self.assertRaisesRegex(
            RuntimeError, "Database missing"
        ):
            run.run()

        self.mock_popen.assert_not_called()

    def test_starts_both_services(self):
        """FastAPI and Streamlit start with correct commands."""
        run.run()

        self.assertEqual(self.mock_popen.call_count, 2)

        backend_command = (
            self.mock_popen.call_args_list[0].args[0]
        )
        frontend_command = (
            self.mock_popen.call_args_list[1].args[0]
        )

        self.assertEqual(
            backend_command,
            [
                str(self.python),
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
        )

        self.assertEqual(
            frontend_command,
            [
                str(self.python),
                "-m",
                "streamlit",
                "run",
                "frontend/app.py",
                "--server.address",
                "127.0.0.1",
                "--server.port",
                "8501",
                "--server.headless",
                "true",
            ],
        )

    def test_checks_service_health(self):
        """Both services receive startup health checks."""
        run.run()

        self.assertEqual(
            self.mock_health.call_args_list,
            [
                call(
                    f"{run.BACKEND_URL}/health",
                    self.backend,
                ),
                call(
                    f"{run.FRONTEND_URL}/_stcore/health",
                    self.frontend,
                ),
            ],
        )

    def test_opens_browser(self):
        """The launcher opens the application URL."""
        run.run()

        self.mock_browser.assert_called_once_with(
            run.FRONTEND_URL
        )

    def test_browser_unavailable(self):
        """Browser unavailability does not stop the application."""
        self.mock_browser.return_value = False

        run.run()

        self.mock_sleep.assert_called_once_with(1)

    def test_browser_error(self):
        """Browser errors do not stop the application."""
        self.mock_browser.side_effect = OSError(
            "Browser unavailable"
        )

        run.run()

        self.mock_sleep.assert_called_once_with(1)

    def test_ctrl_c_stops_both_services(self):
        """Keyboard interruption cleans up both services."""
        run.run()

        self.frontend.terminate.assert_called_once()
        self.backend.terminate.assert_called_once()

    def test_backend_startup_failure(self):
        """Backend failure prevents frontend startup."""
        self.mock_health.side_effect = RuntimeError(
            "Backend startup failed"
        )

        with self.assertRaises(RuntimeError):
            run.run()

        self.assertEqual(self.mock_popen.call_count, 1)
        self.backend.terminate.assert_called_once()
        self.frontend.terminate.assert_not_called()
        self.mock_browser.assert_not_called()

    def test_frontend_startup_failure(self):
        """Frontend startup failure cleans up both services."""
        self.mock_health.side_effect = [
            None,
            RuntimeError("Frontend startup failed"),
        ]

        with self.assertRaises(RuntimeError):
            run.run()

        self.backend.terminate.assert_called_once()
        self.frontend.terminate.assert_called_once()
        self.mock_browser.assert_not_called()

    def test_backend_stops_unexpectedly(self):
        """Unexpected backend termination stops the frontend."""
        self.backend.poll.return_value = 1

        with self.assertRaisesRegex(
            RuntimeError, "Backend stopped unexpectedly"
        ):
            run.run()

        self.frontend.terminate.assert_called_once()

    def test_frontend_stops_unexpectedly(self):
        """Unexpected frontend termination stops the backend."""
        self.frontend.poll.return_value = 1

        with self.assertRaisesRegex(
            RuntimeError, "Frontend stopped unexpectedly"
        ):
            run.run()

        self.backend.terminate.assert_called_once()

    def test_services_do_not_use_shell(self):
        """Application services launch without shell execution."""
        run.run()

        for process_call in self.mock_popen.call_args_list:
            self.assertIs(
                process_call.kwargs["shell"],
                False,
            )


class TestGetVenvPython(unittest.TestCase):

    def test_windows_python_path(self):
        """Windows uses the Scripts directory."""
        venv = Path(".venv")

        self.assertEqual(
            run.get_venv_python(venv, "nt"),
            venv / "Scripts" / "python.exe",
        )

    def test_posix_python_path(self):
        """Linux and macOS use the bin directory."""
        venv = Path(".venv")

        self.assertEqual(
            run.get_venv_python(venv, "posix"),
            venv / "bin" / "python",
        )


class TestMain(unittest.TestCase):

    @patch("run.run")
    def test_successful_startup(self, mock_run):
        """Successful execution returns exit code zero."""
        self.assertEqual(run.main(), 0)
        mock_run.assert_called_once_with()

    @patch("builtins.print")
    @patch("run.run")
    def test_runtime_error(self, mock_run, mock_print):
        """Runtime startup failures return exit code one."""
        mock_run.side_effect = RuntimeError(
            "Service failed."
        )

        self.assertEqual(run.main(), 1)

        mock_print.assert_called_once_with(
            "Startup failed: Service failed."
        )

    @patch("builtins.print")
    @patch("run.run")
    def test_os_error(self, mock_run, mock_print):
        """Operating system failures return exit code one."""
        mock_run.side_effect = OSError(
            "Permission denied."
        )

        self.assertEqual(run.main(), 1)

        mock_print.assert_called_once_with(
            "Startup failed: Permission denied."
        )

    @patch("pathlib.Path.exists", return_value=False)
    @patch("builtins.print")
    def test_script_entry_point(
        self, mock_print, mock_exists
    ):
        """Direct execution exits with the startup result."""
        with self.assertRaises(SystemExit) as context:
            runpy.run_path(
                str(run.ROOT / "run.py"),
                run_name="__main__",
            )

        self.assertEqual(context.exception.code, 1)


if __name__ == "__main__":
    unittest.main()