#!/usr/bin/env python3
"""
Auto-detection: scan environment for API keys → build model pool automatically.

If you have keys → pool is ready. If you don't → you get what's available.
No wizard needed. No agent names hardcoded.

Checks (in order):
  1. Environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
  2. Config files: ~/.openai_key, ~/.glm_key, ~/.deepseek_key, etc.
  3. Local endpoints: ollama on :11434, smart-router on :15728, etc.
  4. Falls back to a minimal "no API key? you get one free-tier model" pool.
"""

import json
import os
import socket
from pathlib import Path

# ── Known API backends ────────────────────────────────────────
# Format: { "provider": { env_vars, key_files, endpoints, tier, strengths, api_type } }

KNOWN_BACKENDS = [
    {
        "name": "glm-5.2",
        "env_vars": ["ZHIPU_API_KEY", "GLM_API_KEY", "BIGMODEL_API_KEY"],
        "key_files": [".glm_key", ".bigmodel_key", ".zhipu_key"],
        "tier": "budget",
        "strengths": ["coding", "code_review", "chinese", "fast"],
        "api_type": "anthropic",
    },
    {
        "name": "gpt-5.5",
        "env_vars": ["OPENAI_API_KEY"],
        "key_files": [".openai_key"],
        "tier": "premium",
        "strengths": ["reasoning", "architecture", "security", "diagnosis", "creative"],
        "api_type": "openai",
    },
    {
        "name": "deepseek-v4-pro",
        "env_vars": ["DEEPSEEK_API_KEY"],
        "key_files": [".deepseek_key"],
        "tier": "standard",
        "strengths": ["chinese", "general", "budget_coding"],
        "api_type": "anthropic",
    },
    {
        "name": "claude-sonnet-4",
        "env_vars": ["ANTHROPIC_API_KEY"],
        "key_files": [".anthropic_key"],
        "tier": "standard",
        "strengths": ["coding", "reasoning", "code_review"],
        "api_type": "anthropic",
    },
    {
        "name": "gemini-3-pro",
        "env_vars": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "key_files": [".google_key", ".gemini_key"],
        "tier": "standard",
        "strengths": ["reasoning", "general", "creative"],
        "api_type": "google",
    },
    # Local / self-hosted models — detected by port check
    {
        "name": "ollama-local",
        "env_vars": [],
        "key_files": [],
        "test_endpoint": "http://localhost:11434/api/tags",
        "local_only": True,
        "tier": "budget",
        "strengths": ["general", "coding"],
        "api_type": "openai_compatible",
    },
]


def _has_env(backend: dict) -> bool:
    for var in backend.get("env_vars", []):
        val = os.environ.get(var, "").strip()
        if val and len(val) > 5:
            return True
    return False


def _has_key_file(backend: dict) -> bool:
    home = Path.home()
    search_dirs = [
        home,
        home / ".config",
        home / ".trinity",
        home / "smart-router",
    ]
    for fname in backend.get("key_files", []):
        for loc in search_dirs:
            path = loc / fname
            if path.exists():
                try:
                    content = path.read_text().strip()
                    if content and len(content) > 5:
                        return True
                except Exception:
                    pass
    return False


def _endpoint_reachable(endpoint: str, timeout: float = 2.0) -> bool:
    """Quick TCP check for LOCAL endpoints only (localhost / private IPs).
    Public cloud APIs always pass TCP check even without valid keys,
    so this is disabled for them via the 'local_only' flag on backends."""
    if not endpoint:
        return False
    try:
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except Exception:
        return False
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False


def scan() -> dict:
    """
    Scan the environment and return a model pool.
    No user input required.
    """
    pool = {}
    
    for backend in KNOWN_BACKENDS:
        name = backend["name"]
        
        # Check in priority order
        found = _has_env(backend) or _has_key_file(backend)
        
        # For local/self-hosted backends, also check if endpoint is reachable
        if not found and backend.get("local_only") and backend.get("test_endpoint"):
            found = _endpoint_reachable(backend["test_endpoint"])
        
        if found:
            pool[name] = {
                "tier": backend["tier"],
                "strengths": backend["strengths"],
                "api_type": backend["api_type"],
            }
    
    # If nothing found at all, give a minimal fallback
    if not pool:
        pool["openai-gpt-4.1-mini"] = {
            "tier": "standard",
            "strengths": ["coding", "general"],
            "api_type": "openai",
        }
    
    return pool


def save_pool(pool: dict, path: Path = None) -> Path:
    """Save pool to file. Returns the path used."""
    if path is None:
        path = Path.home() / ".trinity" / "model_pool.json"
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    
    return path


def init(auto_save: bool = True) -> dict:
    """
    One-call setup: scan and optionally save.
    Import this in trinity-lite's __init__.py or setup.py.
    
    Usage:
        from model_autodetect import init
        pool = init()  # scans, saves, returns pool
    """
    pool = scan()
    
    if auto_save:
        save_pool(pool)
    
    return pool


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    pool = scan()
    
    print("🔍 自动检测结果:")
    if not pool:
        print("  ⚠️  未检测到任何 API key，使用默认配置")
    else:
        print(f"  ✅ 检测到 {len(pool)} 个可用后端:")
        for name, info in pool.items():
            print(f"     • {name} ({info['tier']}) — {', '.join(info['strengths'][:3])}")
    
    path = save_pool(pool)
    print(f"\n  📁 已保存: {path}")
    print(f"  💡 编辑此文件可手动调整模型配置")
