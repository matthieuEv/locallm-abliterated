"""Global, disposable OpenCode V2 + Rapid-MLX setup for Apple Silicon."""

import argparse
import fcntl
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent
MODEL = "Youssofal/Qwen3.6-35B-A3B-Abliterated-Heretic-MLX-4bit"


def fetch_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def latest_v2():
    version = fetch_json("https://opencode.ai/update/api/latest/cli/npm")["version"]
    if re.fullmatch(r"2\.\d+\.\d+", version):
        return version
    versions = fetch_json("https://registry.npmjs.org/@opencode%2fcli")["versions"]
    stable = [v for v in versions if re.fullmatch(r"2\.\d+\.\d+", v)]
    if not stable:
        raise RuntimeError("Aucune version stable OpenCode 2.x disponible.")
    return max(stable, key=lambda v: tuple(map(int, v.split("."))))


def identity(pid):
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "uid=,lstart=,stat="], capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    birth, status = result.stdout.strip().rsplit(None, 1)
    return "" if status.startswith("Z") else birth


def record(process):
    return {"pid": process.pid, "identity": identity(process.pid)}


def stop_process(info, group=False):
    pid = info["pid"]
    if pid <= 1 or not info["identity"] or identity(pid) != info["identity"]:
        return
    send = (lambda sig: os.killpg(pid, sig)) if group else (lambda sig: os.kill(pid, sig))
    try:
        if group and os.getpgid(pid) != pid:
            raise RuntimeError(f"Groupe de processus inattendu pour {pid}; arrêt refusé.")
        send(signal.SIGTERM)
        for _ in range(100):
            if identity(pid) != info["identity"]:
                return
            time.sleep(0.1)
        send(signal.SIGKILL)
    except ProcessLookupError:
        pass


def run(command, **kwargs):
    # Reap installer/server children even when destroy interrupts start.
    process = subprocess.Popen([str(p) for p in command], start_new_session=True, **kwargs)
    info = record(process)
    try:
        code = process.wait()
        if code:
            raise subprocess.CalledProcessError(code, command)
    finally:
        if process.poll() is None:
            stop_process(info, group=True)
        process.wait()


class Setup:
    def __init__(self, home=None, env=None):
        self.home = Path(home or Path.home()).resolve()
        self.env = dict(os.environ if env is None else env)
        self.config_root = Path(self.env.get("XDG_CONFIG_HOME", self.home / ".config"))
        self.data_root = Path(self.env.get("XDG_DATA_HOME", self.home / ".local/share"))
        self.state_root = Path(self.env.get("XDG_STATE_HOME", self.home / ".local/state"))
        self.cache_root = Path(self.env.get("XDG_CACHE_HOME", self.home / ".cache"))
        self.config = self.config_root / "opencode"
        self.state = self.state_root / "locallm-abliterated"
        self.opencode = self.home / ".opencode/bin/opencode"
        self.bin = Path(self.env.get("UV_TOOL_BIN_DIR", self.home / ".local/bin"))
        self.rapid = self.bin / "rapid-mlx"
        hf_home = Path(self.env.get("HF_HOME", self.cache_root / "huggingface"))
        self.hub = Path(self.env.get("HF_HUB_CACHE", hf_home / "hub"))
        self.model_path = self.hub / ("models--" + MODEL.replace("/", "--"))
        self.env.update(RAPID_MLX_TELEMETRY="0", RAPID_MLX_DISABLE_VERSION_CHECK="1",
                        HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")

    def safe_target(self, path):
        target = path.resolve()
        if not path.is_absolute() or target == self.home or target in self.home.parents:
            raise RuntimeError(f"Chemin dangereux : {path}")
        if target == REPO or target in REPO.parents or REPO in target.parents:
            raise RuntimeError(f"Le repo doit rester intact : {path}")

    def remove(self, path):
        # Unlink symlinks themselves; never recursively delete their destinations.
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            self.safe_target(path)
            print(f"Suppression : {path}", flush=True)
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    def save_run(self, owner, rapid=None):
        payload = {"owner": owner, "rapid": rapid}
        temporary = self.state / "run.tmp"
        temporary.write_text(json.dumps(payload))
        temporary.replace(self.state / "run.json")

    def copy_config(self):
        for destination in (self.config, self.config_root / "rapid-mlx"):
            self.safe_target(destination)
            destination.mkdir(parents=True, exist_ok=True)
        config = json.loads((REPO / "config/opencode.json").read_text())
        config["instructions"] = [str(self.config / "local-context.md")]
        # Replace the file rather than following a pre-existing config symlink.
        self.remove(self.config / "opencode.jsonc")
        self.remove(self.config / "opencode.json")
        (self.config / "opencode.json").write_text(json.dumps(config, indent=2) + "\n")
        for name, destination in (
            ("local-context.md", self.config / "local-context.md"),
            ("rapid-mlx.json", self.config_root / "rapid-mlx/locallm.json"),
        ):
            self.remove(destination)
            shutil.copyfile(REPO / "config" / name, destination)

    def lock(self):
        self.safe_target(self.state)
        self.state.mkdir(parents=True, exist_ok=True)
        handle = (self.state / "run.lock").open("w")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise RuntimeError("Un start/destroy est déjà actif. Utilise le terminal existant.")
        return handle

    def check_installations(self):
        for name, expected in (("opencode", self.opencode), ("rapid-mlx", self.rapid)):
            for directory in self.env.get("PATH", "").split(os.pathsep):
                candidate = Path(directory) / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    if candidate.resolve() != expected.resolve():
                        raise RuntimeError(
                            f"Installation concurrente : {candidate}. Désinstalle-la avec son gestionnaire avant start."
                        )

    def check_space(self):
        self.hub.mkdir(parents=True, exist_ok=True)
        info = fetch_json(f"https://huggingface.co/api/models/{MODEL}?blobs=true")
        needed = 0
        revision = info["sha"]
        for item in info["siblings"]:
            cached = self.model_path / "snapshots" / revision / item["rfilename"]
            if not cached.is_file():
                needed += item.get("size", 0)
        reserve = 6 * 1024**3
        free = shutil.disk_usage(self.hub).free
        if free < needed + reserve:
            raise RuntimeError(
                f"Espace insuffisant : {free / 1024**3:.1f} Gio libres, "
                f"{needed / 1024**3:.1f} Gio à télécharger + 6 Gio de réserve requis."
            )

    def start(self, project, arguments):
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise RuntimeError("Rapid-MLX nécessite macOS sur Apple Silicon (sans Rosetta).")
        settings = json.loads((REPO / "config/rapid-mlx.json").read_text())
        config = json.loads((REPO / "config/opencode.json").read_text())
        limit = config["providers"]["rapid-mlx"]["models"][MODEL]["limit"]
        if settings["model"] != MODEL or config["model"] != "rapid-mlx/" + MODEL:
            raise RuntimeError("Modèles OpenCode/Rapid-MLX incohérents.")
        if limit["input"] + limit["output"] > limit["context"]:
            raise RuntimeError("Les budgets entrée + sortie dépassent le contexte.")
        for flag, name in (("--context-length", "context"), ("--max-prompt-tokens", "input"), ("--max-tokens", "output")):
            if int(settings["flags"][settings["flags"].index(flag) + 1]) != limit[name]:
                raise RuntimeError(f"Budget {name} différent entre OpenCode et Rapid-MLX.")
        self.check_installations()
        with self.lock():
            owner = {"pid": os.getpid(), "identity": identity(os.getpid())}
            self.save_run(owner)
            rapid = None
            rapid_info = None
            try:
                try:
                    with socket.socket() as probe:
                        probe.bind(("127.0.0.1", 8000))
                except OSError as error:
                    raise RuntimeError("Port 8000 occupé. Arrête le serveur existant avant start.") from error
                self.check_space()
                if self.opencode.exists():
                    run([self.opencode, "service", "stop"], env=self.env)
                version = latest_v2()
                print(f"Installation OpenCode stable {version}", flush=True)
                with tempfile.TemporaryDirectory(prefix="locallm-install-") as directory:
                    installer = Path(directory) / "install.sh"
                    with urllib.request.urlopen("https://opencode.ai/v2/install", timeout=60) as response:
                        installer.write_bytes(response.read())
                    run(["bash", installer, "--version", version, "--no-modify-path"], env=self.env)
                installed = subprocess.check_output([self.opencode, "--version"], env=self.env, text=True).strip()
                if installed != version:
                    raise RuntimeError(f"Version OpenCode inattendue : {installed}")
                run(["uv", "tool", "install", "--python", "3.12", "--upgrade", "--no-cache",
                     f"rapid-mlx=={settings['version']}"], env=self.env)
                run([self.rapid, "pull", MODEL], env=self.env)
                self.copy_config()
                log_dir = self.state / "logs" / (time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}")
                log_dir.mkdir(parents=True, exist_ok=True)
                current = self.state / "current"
                current.unlink(missing_ok=True)
                current.symlink_to(log_dir.relative_to(self.state), target_is_directory=True)
                print(f"Logs : {current}\nChargement du modèle…", flush=True)
                with (log_dir / "rapid-mlx.log").open("w") as log:
                    rapid = subprocess.Popen(
                        [str(self.rapid), "serve", MODEL, *settings["flags"], "--watchdog-ppid", str(os.getpid())],
                        stdout=log, stderr=subprocess.STDOUT, env=self.env, start_new_session=True,
                    )
                    rapid_info = record(rapid)
                    self.save_run(owner, rapid_info)
                    self.wait_ready(rapid)
                    with (log_dir / "opencode.log").open("w") as errors:
                        self.launch_opencode(project, arguments, errors)
            finally:
                if rapid is not None:
                    if rapid.poll() is None:
                        stop_process(rapid_info, group=True)
                    rapid.wait()
                (self.state / "run.json").unlink(missing_ok=True)
                if rapid is not None:
                    print("Rapid-MLX arrêté. Installation conservée jusqu’à ./locallm destroy.", flush=True)

    def wait_ready(self, process):
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Rapid-MLX a échoué. Voir {self.state / 'current/rapid-mlx.log'}")
            try:
                fetch_json("http://127.0.0.1:8000/health/ready", timeout=2)
                models = fetch_json("http://127.0.0.1:8000/v1/models", timeout=2)["data"]
                if MODEL not in [model["id"] for model in models]:
                    raise RuntimeError("Le serveur expose un autre modèle.")
                return
            except (urllib.error.URLError, TimeoutError):
                time.sleep(1)
        raise RuntimeError("Rapid-MLX indisponible après 10 minutes; consulter les logs.")

    def launch_opencode(self, project, arguments, errors):
        env = dict(self.env, PWD=str(project))
        process = subprocess.Popen(
            [str(self.opencode), "--standalone", "--print-logs", "--log-level", "info", str(project), *arguments],
            cwd=project, env=env, stderr=errors,
        )
        try:
            code = process.wait()
            if code:
                raise subprocess.CalledProcessError(code, process.args)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

    def destroy(self):
        active = self.state / "run.json"
        if active.exists():
            info = json.loads(active.read_text())
            stop_process(info["owner"])
            if info.get("rapid"):
                stop_process(info["rapid"], group=True)
        with self.lock():
            if self.opencode.exists():
                run([self.opencode, "service", "stop"], env=self.env)
            # Uninstall through uv so all Rapid-MLX aliases and its venv disappear.
            tools = subprocess.check_output(["uv", "tool", "list"], env=self.env, text=True)
            if re.search(r"^rapid-mlx v", tools, re.M):
                run(["uv", "tool", "uninstall", "rapid-mlx"], env=self.env)
            paths = [
                self.home / ".opencode", self.config, self.data_root / "opencode",
                self.state_root / "opencode", self.cache_root / "opencode",
                Path(tempfile.gettempdir()) / "opencode", self.config_root / "rapid-mlx",
                self.home / ".rapid-mlx", self.cache_root / "rapid-mlx", self.state_root / "rapid-mlx",
                self.bin / "start-rapid-mlx", self.bin / "bench-rapid-mlx", self.model_path,
                self.hub / ".locks" / self.model_path.name,
            ]
            # Validate every recursive target before deleting the first one.
            for path in paths + [self.state]:
                if not path.is_symlink():
                    self.safe_target(path)
            for path in paths:
                self.remove(path)
            self.remove(self.state)
        print("Setup supprimé, y compris sessions et modèle. Repo conservé.", flush=True)


def interrupted(*_):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="Installer, configurer et lancer OpenCode")
    start.add_argument("project", nargs="?", default=os.getcwd())
    start.add_argument("arguments", nargs=argparse.REMAINDER)
    commands.add_parser("destroy", help="Effacer installation globale, sessions et modèle sans sauvegarde")
    args = parser.parse_args()
    os.umask(0o077)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        setup = Setup()
        if args.command == "start":
            project = Path(args.project).expanduser().resolve(strict=True)
            if not project.is_dir():
                raise RuntimeError(f"Ce n’est pas un dossier : {project}")
            setup.start(project, args.arguments)
        else:
            setup.destroy()
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
