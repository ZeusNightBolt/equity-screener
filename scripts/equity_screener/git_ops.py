import subprocess

from .config import GIT_TRACKED_OUTPUTS, PROJECT_DIR

def git_commit_push() -> None:
    subprocess.run(["git", "add", *GIT_TRACKED_OUTPUTS], cwd=PROJECT_DIR, check=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_DIR, text=True, capture_output=True, check=True).stdout.strip()
    if not status:
        print("git: no changes to commit")
        return
    subprocess.run(["git", "commit", "-m", "Update Equity Screener dashboard"], cwd=PROJECT_DIR, check=True)
    remotes = subprocess.run(["git", "remote"], cwd=PROJECT_DIR, text=True, capture_output=True, check=True).stdout.strip().splitlines()
    if "origin" in remotes:
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=PROJECT_DIR, text=True, capture_output=True, check=True).stdout.strip()
        if not branch:
            branch = "HEAD"
        subprocess.run(["git", "push", "origin", branch], cwd=PROJECT_DIR, check=True)
