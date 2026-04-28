import os
import shutil
import sys
from utils.skill_path import resolve_skill_root


def _prepend_path(path: str) -> None:
    if not path or not os.path.isdir(path):
        return
    current_paths = os.environ.get("PATH", "").split(os.pathsep)
    normalized = os.path.normcase(os.path.abspath(path))
    exists = any(
        os.path.normcase(os.path.abspath(item)) == normalized
        for item in current_paths
        if item
    )
    if exists:
        return
    os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")


def _ensure_ffprobe_path(skill_root: str | None = None) -> None:
    if shutil.which("ffprobe"):
        return

    candidate_dirs = []
    for env_name in ("FFPROBE_PATH", "FFMPEG_PATH", "FFMPEG_HOME"):
        env_value = os.environ.get(env_name)
        if not env_value:
            continue
        if os.path.isfile(env_value):
            candidate_dirs.append(os.path.dirname(env_value))
        else:
            candidate_dirs.extend([env_value, os.path.join(env_value, "bin")])

    if skill_root:
        candidate_dirs.extend(
            [
                os.path.join(skill_root, "bin"),
                os.path.join(skill_root, "tools", "ffmpeg", "bin"),
                os.path.join(skill_root, "tools", "ffmpeg"),
                os.path.join(skill_root, "scripts", "vendor", "ffmpeg", "bin"),
            ]
        )

    candidate_dirs.extend(
        [
            r"C:\ffmpeg\bin",
            r"C:\Program Files\ffmpeg\bin",
            r"C:\ProgramData\chocolatey\bin",
            os.path.expanduser(r"~\scoop\shims"),
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/usr/bin",
        ]
    )

    executable = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    for directory in candidate_dirs:
        if directory and os.path.exists(os.path.join(directory, executable)):
            _prepend_path(directory)
            return

def setup_env():
    """
    统一初始化 JianYing Editor Skill 运行环境。
    将 scripts、vendor 及跨 Skill 的依赖路径注入到 sys.path 中。
    """
    try:
        current_frame = sys._getframe(1)
        caller_file = current_frame.f_globals.get('__file__')
        if caller_file:
            start_dir = os.path.dirname(os.path.abspath(caller_file))
        else:
            start_dir = os.getcwd()
    except Exception:
        start_dir = os.getcwd()

    skill_root, _ = resolve_skill_root(start_dir)
    _ensure_ffprobe_path(skill_root)
            
    if skill_root:
        scripts_dir = os.path.join(skill_root, "scripts")
        vendor_dir = os.path.join(scripts_dir, "vendor")
        
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
            
        if vendor_dir not in sys.path:
            sys.path.insert(0, vendor_dir)
            
        possible_api_roots = [
            os.path.join(skill_root, "..", "antigravity-api-skill", "libs"),
            os.path.abspath(os.path.join(skill_root, "../../antigravity-api-skill/libs"))
        ]
        for api_path in possible_api_roots:
            if os.path.exists(api_path) and api_path not in sys.path:
                sys.path.append(api_path)
                break
