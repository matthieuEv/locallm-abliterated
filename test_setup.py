import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import setup


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="locallm-test-")
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.app = setup.Setup(home=self.home, env={"PATH": "/usr/bin:/bin"})

    def test_model_and_budgets_match(self):
        config = json.loads((setup.REPO / "config/opencode.json").read_text())
        rapid = json.loads((setup.REPO / "config/rapid-mlx.json").read_text())
        model = config["providers"]["rapid-mlx"]["models"][setup.MODEL]
        limit = model["limit"]
        self.assertEqual(rapid["model"], setup.MODEL)
        self.assertEqual(config["model"], "rapid-mlx/" + setup.MODEL)
        self.assertEqual(limit["input"] + limit["output"], limit["context"])
        for flag, name in (("--context-length", "context"), ("--max-prompt-tokens", "input"), ("--max-tokens", "output")):
            self.assertEqual(int(rapid["flags"][rapid["flags"].index(flag) + 1]), limit[name])
        self.assertEqual(limit["input"] - config["compaction"]["buffer"], 26624)
        self.assertNotIn("websearch", config)

    def test_copy_replaces_conflict_and_does_not_follow_file_symlinks(self):
        self.app.config.mkdir(parents=True)
        secret = self.home / "keep.txt"
        secret.write_text("untouched")
        (self.app.config / "opencode.json").symlink_to(secret)
        (self.app.config / "opencode.jsonc").write_text("old")
        (self.app.config / "auth.json").write_text("credentials")
        self.app.copy_config()
        self.assertEqual(secret.read_text(), "untouched")
        self.assertFalse((self.app.config / "opencode.jsonc").exists())
        self.assertEqual((self.app.config / "auth.json").read_text(), "credentials")
        config = json.loads((self.app.config / "opencode.json").read_text())
        self.assertEqual(config["instructions"], [str(self.app.config / "local-context.md")])

    def test_destroy_removes_global_data_and_model_but_keeps_other_models_and_projects(self):
        self.app.copy_config()
        for path in (self.app.data_root / "opencode", self.app.home / ".opencode", self.app.model_path):
            path.mkdir(parents=True, exist_ok=True)
            (path / "data").write_text("delete")
        other_model = self.app.hub / "models--another--model"
        other_model.mkdir()
        project = self.home / "project"
        project.mkdir()
        (project / "code.py").write_text("keep")
        with patch("setup.run") as run, patch("setup.subprocess.check_output", return_value="rapid-mlx v0.16.6\n"), patch("setup.tempfile.gettempdir", return_value=str(self.home / "tmp")):
            self.app.destroy()
            run.assert_called_once_with(["uv", "tool", "uninstall", "rapid-mlx"], env=self.app.env)
            self.app.destroy()  # already deleted data: still safe
        self.assertFalse(self.app.config.exists())
        self.assertFalse(self.app.model_path.exists())
        self.assertFalse((self.app.data_root / "opencode").exists())
        self.assertFalse(self.app.state.exists())
        self.assertTrue(other_model.exists())
        self.assertEqual((project / "code.py").read_text(), "keep")

    def test_refuses_to_delete_home_or_repository(self):
        for path in (self.home, self.home.parent, setup.REPO, setup.REPO / "config"):
            with self.assertRaises(RuntimeError):
                self.app.safe_target(path)

    def test_symlink_cleanup_keeps_destination(self):
        destination = self.home / "keep"
        destination.mkdir()
        (destination / "file").write_text("keep")
        link = self.home / "remove"
        link.symlink_to(destination, target_is_directory=True)
        self.app.remove(link)
        self.assertEqual((destination / "file").read_text(), "keep")

    def test_latest_v2_rejects_prerelease_and_future_major(self):
        with patch("setup.fetch_json", side_effect=[{"version": "3.0.0"}, {"versions": {"2.9.0": {}, "2.10.0": {}, "2.11.0-beta": {}, "3.0.0": {}}}]):
            self.assertEqual(setup.latest_v2(), "2.10.0")

    def test_low_disk_space_aborts(self):
        with patch("setup.fetch_json", return_value={"sha": "rev", "siblings": [{"rfilename": "weights", "size": 24 * 1024**3}]}), patch("setup.shutil.disk_usage", return_value=type("Disk", (), {"free": 8 * 1024**3})()):
            with self.assertRaisesRegex(RuntimeError, "Espace insuffisant"):
                self.app.check_space()

    def test_does_not_signal_a_reused_pid(self):
        with patch("setup.identity", return_value="other birth time"), patch("setup.os.kill") as kill:
            setup.stop_process({"pid": 1234, "identity": "old birth time"})
            kill.assert_not_called()

    def test_busy_port_does_not_install_or_overwrite_config(self):
        with patch("setup.socket.socket") as socket, patch("setup.run") as run, patch("setup.identity", return_value="test owner"), patch("setup.Setup.check_installations"), patch("setup.platform.system", return_value="Darwin"), patch("setup.platform.machine", return_value="arm64"):
            socket.return_value.__enter__.return_value.bind.side_effect = OSError("occupied")
            with self.assertRaisesRegex(RuntimeError, "Port 8000 occupé"):
                self.app.start(self.home, [])
            run.assert_not_called()
            self.assertFalse(self.app.config.exists())
            self.assertFalse((self.app.state / "run.json").exists())

    def test_server_is_stopped_after_tui_exit_and_startup_failure(self):
        for failure in (False, True):
            with self.subTest(startup_failure=failure), ExitStack() as stack:
                stack.enter_context(patch("setup.platform.system", return_value="Darwin"))
                stack.enter_context(patch("setup.platform.machine", return_value="arm64"))
                stack.enter_context(patch("setup.Setup.check_installations"))
                stack.enter_context(patch("setup.Setup.check_space"))
                stack.enter_context(patch("setup.socket.socket"))
                stack.enter_context(patch("setup.identity", return_value="test identity"))
                stack.enter_context(patch("setup.run"))
                stack.enter_context(patch("setup.latest_v2", return_value="2.1.2"))
                stack.enter_context(patch("setup.subprocess.check_output", return_value="2.1.2"))
                stack.enter_context(patch("setup.urllib.request.urlopen"))
                stack.enter_context(patch("setup.record", return_value={"pid": 1234, "identity": "test identity"}))
                process = Mock(pid=1234)
                process.poll.return_value = None
                popen = stack.enter_context(patch("setup.subprocess.Popen", return_value=process))
                stop = stack.enter_context(patch("setup.stop_process"))
                ready = stack.enter_context(patch.object(self.app, "wait_ready"))
                tui = stack.enter_context(patch.object(self.app, "launch_opencode"))
                response = stack.enter_context(patch("setup.urllib.request.urlopen"))
                response.return_value.__enter__.return_value.read.return_value = b"installer"
                if failure:
                    ready.side_effect = RuntimeError("failed to load")
                    with self.assertRaisesRegex(RuntimeError, "failed to load"):
                        self.app.start(self.home, [])
                    tui.assert_not_called()
                else:
                    self.app.start(self.home, ["-s", "test-session"])
                    tui.assert_called_once()
                self.assertIn(setup.MODEL, popen.call_args.args[0])
                self.assertIn("--watchdog-ppid", popen.call_args.args[0])
                stop.assert_called_once_with({"pid": 1234, "identity": "test identity"}, group=True)
                process.wait.assert_called_once()
                self.assertFalse((self.app.state / "run.json").exists())


if __name__ == "__main__":
    unittest.main()
