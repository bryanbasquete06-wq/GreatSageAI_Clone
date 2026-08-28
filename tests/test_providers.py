# -*- coding: utf-8 -*-
"""Test all providers."""
import os, sys, time
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_here)
sys.path.insert(0, _project_root)
from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, ".env"))
from core.providers import ALL_FREE_PROVIDERS, _key

results = []
for name, prov_cls, score, env_key in ALL_FREE_PROVIDERS:
    try:
        if name in ("9router", "ollama"):
            p = prov_cls()
        elif env_key:
            k = _key(env_key)
            if not k:
                results.append((name, "NO_KEY", score, ""))
                continue
            p = prov_cls(k)
        else:
            results.append((name, "NO_KEY", score, ""))
            continue

        avail = p.available()
        if not avail:
            results.append((name, "UNAVAILABLE", score, ""))
            continue

        t0 = time.time()
        try:
            resp = p.complete(
                [{"role": "user", "content": "Say only: OK"}],
                model=None, max_tokens=10,
            )
            latency = time.time() - t0
            # LLMResult has .content attribute
            text = getattr(resp, "content", None) or ""
            if text and len(text) > 0:
                results.append((name, "OK", score, f"{latency:.1f}s {text[:40]}"))
            else:
                err = getattr(resp, "error", "empty response")
                results.append((name, "EMPTY", score, str(err)[:60]))
        except Exception as e:
            latency = time.time() - t0
            results.append((name, "FAIL", score, f"{latency:.1f}s {str(e)[:80]}"))
    except Exception as e:
        results.append((name, "CRASH", score, str(e)[:80]))

print("=" * 70)
ok = 0
for name, status, sc, extra in results:
    icon = "OK" if status == "OK" else "--"
    if status == "OK": ok += 1
    print(f"  [{icon}] {name:15s} {status:12s} {extra}")
print(f"\n  Funcionando: {ok}/{len(results)}")
print("=" * 70)
