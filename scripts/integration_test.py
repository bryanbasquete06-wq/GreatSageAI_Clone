# -*- coding: utf-8 -*-
"""Integration test — ONLY project modules."""

import sys, os, importlib
from pathlib import Path

# Must be run from project root
PROJECT = Path(__file__).resolve().parent.parent
os.chdir(str(PROJECT))
sys.path = [str(PROJECT)]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

passed = 0
failed = 0
fail_list = []

print("=" * 60)
print("  TEST 1: Import all Elivea project modules")
print("=" * 60)

# Only scan the project directory itself
for f in sorted(PROJECT.glob("*.py")):
    mod = f.stem
    if mod.startswith("test_") or mod == "setup":
        continue
    try:
        importlib.import_module(mod)
        passed += 1
    except Exception as e:
        failed += 1
        fail_list.append((mod, f"{type(e).__name__}: {e}"))
        print(f"  FAIL  {mod}: {type(e).__name__}: {str(e)[:100]}")

for subdir in ["core", "ui", "modules", "memory"]:
    pkg = PROJECT / subdir
    if not pkg.exists():
        continue
    for f in sorted(pkg.rglob("*.py")):
        if "__pycache__" in str(f) or "test_" in f.name:
            continue
        rel = f.relative_to(PROJECT)
        mod = str(rel).replace(os.sep, ".").replace("/", ".")
        if mod.endswith(".__init__"):
            mod = mod[:-9]
        elif mod.endswith(".py"):
            mod = mod[:-3]
        try:
            importlib.import_module(mod)
            passed += 1
        except Exception as e:
            failed += 1
            fail_list.append((mod, f"{type(e).__name__}: {e}"))
            print(f"  FAIL  {mod}: {type(e).__name__}: {str(e)[:100]}")

print(f"\n  Result: {passed} OK, {failed} FAILED")

# === TEST 2: Full app instantiation ===
print("\n" + "=" * 60)
print("  TEST 2: Full EliveaApp instantiation")
print("=" * 60)

try:
    from elvea_app import EliveaApp
    print("  [OK] EliveaApp imported")
except Exception as e:
    print(f"  [FAIL] EliveaApp import: {e}")
    sys.exit(1)

try:
    app = EliveaApp()
    print("  [OK] EliveaApp() created")
    if hasattr(app, '_init_errors') and app._init_errors:
        print(f"  [WARN] {len(app._init_errors)} non-fatal init errors:")
        for name in app._init_errors:
            print(f"         - {name}")
except Exception as e:
    print(f"  [FAIL] EliveaApp() crashed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# === TEST 3: Critical components ===
print("\n" + "=" * 60)
print("  TEST 3: Critical components")
print("=" * 60)

checks = [
    ('llm', 'LLM Engine'), ('persistent_memory', 'Persistent Memory'),
    ('signals', 'Signal Bridge'), ('speech', 'Speech Engine'),
    ('pipeline', 'Voice Pipeline'), ('autonomous', 'Autonomous Engine'),
    ('cot', 'Chain of Thought'), ('nine_router', 'Nine Router'),
]
for attr, label in checks:
    obj = getattr(app, attr, None)
    status = "[OK]" if obj else "[WARN]"
    print(f"  {status} {label}: {type(obj).__name__ if obj else 'None'}")

# === TEST 4: DB health ===
print("\n" + "=" * 60)
print("  TEST 4: Database health")
print("=" * 60)
try:
    import sqlite3
    conn = sqlite3.connect(str(app.persistent_memory.db_path))
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    conn.close()
    print(f"  [OK] DB healthy: {count} memories")
except Exception as e:
    print(f"  [FAIL] DB: {e}")

# === TEST 5: Chat command ===
print("\n" + "=" * 60)
print("  TEST 5: Chat command")
print("=" * 60)
try:
    response = app._handle_command("status")
    print(f"  [OK] 'status' returned {len(response)} chars" if response else "  [WARN] empty")
except Exception as e:
    print(f"  [FAIL] {e}")

# === Summary ===
print("\n" + "=" * 60)
print(f"  SUMMARY: {passed} modules OK, {failed} FAILED")
if fail_list:
    for mod, err in fail_list:
        print(f"    - {mod}: {err}")
print("=" * 60)
