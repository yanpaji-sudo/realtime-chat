# Isolated Berlin test build only; never deploys to the formal branch.
from pathlib import Path
root = Path("member-tree")
replacements = [
    ("磐石", "柏林"),
    ("Panshi", "Berlin"),
    ("panshi", "berlin"),
]
text_suffixes = {".py", ".html", ".js", ".css", ".json", ".md", ".txt", ".yml", ".yaml", ".toml"}
changed = []
for path in sorted(root.rglob("*")):
    if not path.is_file() or path.suffix.lower() not in text_suffixes:
        continue
    try:
        original = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    updated = original
    for old, new in replacements:
        updated = updated.replace(old, new)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        changed.append(str(path))
for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
    if path.name and any(old in path.name for old, _ in replacements):
        new_name = path.name
        for old, new in replacements:
            new_name = new_name.replace(old, new)
        path.rename(path.with_name(new_name))
print(f"Berlin brand replacements completed; changed {len(changed)} files.")
for item in changed:
    print(item)

# Rebuild trigger: fast-forward-safe package publish.
