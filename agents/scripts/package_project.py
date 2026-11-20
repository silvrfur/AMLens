"""Rebuild a clean deliverable ZIP from source; run from any working directory."""
from pathlib import Path
import zipfile

PACKAGE = Path(__file__).resolve().parents[1]
DESTINATION = PACKAGE.parent / 'TraceIQ_Member3_Agentic_AI.zip'
EXCLUDE = {'__pycache__', '.pytest_cache', '.venv', '.git', '.env'}

def main():
    with zipfile.ZipFile(DESTINATION, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob('*')):
            if not path.is_file() or any(part in EXCLUDE for part in path.relative_to(PACKAGE).parts):
                continue
            if path.suffix == '.pyc' or path.name.endswith(('-wal','-shm')) or path.name == 'demo_runtime.db':
                continue
            archive.write(path, path.relative_to(PACKAGE.parent))
    with zipfile.ZipFile(DESTINATION) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert 'agents/data/synthetic_alerts.db' in names
        assert 'agents/.env.example' in names
        assert not any(any(part in EXCLUDE for part in Path(name).parts) for name in names)
        print(f'{DESTINATION}: {len(names)} files, {DESTINATION.stat().st_size} bytes, CRC check passed')

if __name__ == '__main__':
    main()
