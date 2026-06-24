#!/usr/bin/env python3
"""
Model Selector for Trinity — picks the best LLM backend per task.

CONFIG-DRIVEN. No hardcoded model names. Users define their own pool.
The selector only reasons about tiers (budget/standard/premium) and
strength tags (coding/reasoning/chinese/...).

Layered routing:
  1. Fast bypass: deterministic regex rules
  2. Hard signal: keyword → task_demand (security/architecture/diagnosis/...)
  3. SC classify: Selector Complexity 0-3 → tier
  4. Within tier: match task_demand ↔ model strengths

Architecture:
  Hermes → resolve_route() → agent (who)
         → select_model()  → model (with what)
         → dispatch(task, agent, model)
"""

import json
import os
import re
from pathlib import Path

# ── Default model pool (overridable via config/env) ──────────
# Users with only 2 models just list those two here.

DEFAULT_MODEL_POOL = {
    "glm-5.2": {
        "tier": "budget",
        "strengths": ["coding", "code_review", "chinese", "fast", "agentic"],
        "cost": "$1.40/$4.40 per 1M",
        "api_type": "anthropic",
    },
    "gpt-5.5": {
        "tier": "premium",
        "strengths": ["reasoning", "architecture", "security", "diagnosis", "creative"],
        "cost": "$15/$60 per 1M",
        "api_type": "openai",
    },
    "deepseek-v4-pro": {
        "tier": "standard",
        "strengths": ["chinese", "general", "budget_coding"],
        "cost": "$1.50/$6 per 1M",
        "api_type": "anthropic",
    },
}

# ── Task demands → required tier ──────────────────────────────

SC_TIER_MAP = {
    0: "budget",     # trivial/single-step
    1: "budget",     # multi-step/CRUD
    2: "standard",   # complex
    3: "premium",    # entangled/critical
}

TASK_TYPE_TIER = {
    "code_review":          "budget",     # GLM 审查够用, Fugu 同款优势
    "crud_operation":       "budget",
    "bug_fix_simple":       "budget",
    "test_writing":         "budget",
    "test_verification":    "budget",
    "documentation":        "budget",
    "docs_writing":         "budget",
    "architecture_design":  "premium",
    "security_audit":       "premium",
    "bug_fix_complex":      "standard",
    "refactor":             "standard",
    "diagnosis":            "premium",
    "research":             "premium",
    "project_audit":        "premium",
    "feature_implementation": None,  # SC decides
    "deployment":            "standard",
}

# ── Hard signal keywords → task demand tags ───────────────────

HARD_SIGNALS = [
    {
        "keywords": ["安全审计", "security audit", "漏洞", "vulnerability",
                     "渗透", "penetration", "CVE", "exploit", "zero-day"],
        "demands": ["security"],
        "tier_min": "premium",
    },
    {
        "keywords": ["架构", "architecture", "设计模式", "design pattern",
                     "系统设计", "system design", "微服务", "microservice"],
        "demands": ["architecture"],
        "tier_min": "premium",
    },
    {
        "keywords": ["深度分析", "deep analysis", "根因", "root cause",
                     "复杂诊断", "complex diagnosis", "troubleshoot"],
        "demands": ["diagnosis"],
        "tier_min": "premium",
    },
    {
        "keywords": ["性能优化", "performance optimization", "profiling",
                     "瓶颈", "bottleneck"],
        "demands": ["reasoning"],
        "tier_min": "standard",
    },
    {
        "keywords": ["重构", "refactor", "大改", "overhaul", "重写", "rewrite"],
        "demands": ["architecture"],
        "tier_min": "standard",
    },
    {
        "keywords": ["数据库迁移", "migration", "schema change", "DDL"],
        "demands": ["reasoning"],
        "tier_min": "standard",
    },
    {
        "keywords": ["部署", "deploy", "CI/CD", "pipeline", "生产环境", "production"],
        "demands": ["reasoning"],
        "tier_min": "standard",
    },
]

# ── Fast bypass: too trivial to need decision ─────────────────

BYPASS_RULES = [
    (r"^(你好|hi|hello|hey)\b",              "budget"),
    (r"^(say|echo|repeat)\s",                "budget"),
    (r"\b(fix typo|typo fix|拼写|错别字)\b",   "budget"),
    (r"\b(翻译|translate)\b",                 "budget"),
    (r"\b(rename|重命名)\b",                  "budget"),
    (r"\b(add comment|加注释|写注释)\b",        "budget"),
]

# ── SC classification ─────────────────────────────────────────

STRUCTURAL_MARKERS = [
    (r"(多个文件|multi.?file|across files)", 1),
    (r"(refactor|重构|rewrite|重写|restructure)", 1),
    (r"(debug|调试|fix bug|修复|troubleshoot|排查)", 1),
    (r"(review|审查|audit|审计)", 1),
    (r"(document|文档|README|docstring|注释)", 0),
    (r"(test|测试|unittest|pytest|spec)", 0),
]


def load_model_pool(pool_path: str = None) -> dict:
    """Load user's model pool from JSON file, or use defaults."""
    if pool_path is None:
        # Check env var, then default locations
        pool_path = os.environ.get("TRINITY_MODEL_POOL", "")
        if not pool_path:
            for candidate in [
                Path.home() / ".hermes" / "model_pool.json",
                Path.home() / ".trinity" / "model_pool.json",
                Path("model_pool.json"),
            ]:
                if candidate.exists():
                    pool_path = str(candidate)
                    break
    
    if pool_path and Path(pool_path).exists():
        with open(pool_path) as f:
            return json.load(f)
    
    return DEFAULT_MODEL_POOL


def _tier_rank(tier: str) -> int:
    return {"budget": 0, "standard": 1, "premium": 2}.get(tier, 1)


def _pick_best_model(pool: dict, tier: str, demands: list = None, agent: str = None) -> str:
    """
    Pick the best model from the pool given a tier requirement.
    
    Rules:
    0. Filter: only models available to this agent (if agent specified)
    1. Any model at tier or above qualifies
    2. Among qualifiers, prefer exact tier match (budget→budget, etc.)
    3. If no tag match, pick the highest-tier model
    4. If only one model in pool, always pick that one
    """
    if not pool:
        return None
    
    # Filter: only models this agent can use
    eligible = {}
    for name, info in pool.items():
        available = info.get("available_to")
        if available is None:
            eligible[name] = info  # no restriction → anyone can use
        elif not agent:
            eligible[name] = info  # no agent specified → don't filter
        elif agent in available:
            eligible[name] = info
    
    if not eligible:
        return None  # no compatible model for this agent
    if len(eligible) == 1:
        return list(eligible.keys())[0]
    
    demands = demands or []
    min_rank = _tier_rank(tier)
    
    qualified = []
    for name, info in eligible.items():
        model_tier = info.get("tier", "standard")
        if _tier_rank(model_tier) >= min_rank:
            model_strengths = set(info.get("strengths", []))
            tag_match = len(set(demands) & model_strengths)
            tier_match_bonus = 1 if model_tier == tier else 0
            qualified.append((tag_match, tier_match_bonus, _tier_rank(model_tier), name))
    
    if not qualified:
        # No model meets tier — pick highest tier available
        best = max(eligible.items(), key=lambda x: _tier_rank(x[1].get("tier", "standard")))
        return best[0]
    
    qualified.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return qualified[0][3]


def select_model(
    task: str,
    task_type: str = None,
    agent: str = None,
    force_model: str = None,
    pool_path: str = None,
    debug: bool = False,
) -> dict:
    """Pick the best model for a task from the user's model pool."""
    
    pool = load_model_pool(pool_path)
    
    if force_model:
        if force_model in pool:
            return _result(force_model, "forced", "force", pool)
        return _result(force_model, "forced (not in pool)", "force", pool)

    task_lower = task.lower().strip()
    _d = lambda msg: print(f"  [model_selector] {msg}") if debug else None

    # Layer 1: Fast bypass
    for pattern, tier in BYPASS_RULES:
        if re.search(pattern, task_lower):
            model = _pick_best_model(pool, tier, agent=agent)
            _d(f"BYPASS → tier={tier} → {model}")
            return _result(model, f"bypass→tier:{tier}", "bypass", pool)

    # Layer 2: Hard signals
    for rule in HARD_SIGNALS:
        if any(kw in task_lower for kw in rule["keywords"]):
            demands = rule.get("demands", [])
            tier = rule.get("tier_min", "standard")
            model = _pick_best_model(pool, tier, demands, agent=agent)
            _d(f"HARD SIGNAL: {demands} tier≥{tier} → {model}")
            return _result(model, f"signal:{demands[0] if demands else '?'}", "hard_signal", pool)

    # Layer 2.5: Task type tier map
    if task_type and task_type in TASK_TYPE_TIER:
        mapped_tier = TASK_TYPE_TIER[task_type]
        if mapped_tier:
            model = _pick_best_model(pool, mapped_tier, agent=agent)
            _d(f"TASK_TYPE: {task_type} tier={mapped_tier} → {model}")
            return _result(model, f"task_type:{task_type}", "task_type_map", pool)

    # Layer 3: SC classification
    sc_level = _sc_classify(task)
    tier = SC_TIER_MAP.get(sc_level, "standard")
    model = _pick_best_model(pool, tier, agent=agent)
    sc_names = {0: "trivial", 1: "simple", 2: "complex", 3: "critical"}
    _d(f"SC: {sc_names.get(sc_level,'?')} (L{sc_level}) → tier={tier} → {model}")
    return _result(model, f"sc:L{sc_level}", "sc_classify", pool, sc_level=sc_level)


def _sc_classify(task: str) -> int:
    """Estimate Selector Complexity level (0-3)."""
    task_lower = task.lower()
    token_count = len(task.split())
    
    base_sc = 0
    if token_count >= 800:
        base_sc = 3
    elif token_count >= 300:
        base_sc = 2
    elif token_count >= 100:
        base_sc = 1
    
    adjustment = 0
    for pattern, delta in STRUCTURAL_MARKERS:
        if re.search(pattern, task_lower):
            adjustment += delta
    
    return min(3, max(0, base_sc + adjustment))


def _result(model, reason, method, pool, sc_level=None):
    info = pool.get(model, {})
    return {
        "model": model,
        "reason": reason,
        "method": method,
        "sc_level": sc_level,
        "tier": info.get("tier", "?"),
        "cost": info.get("cost", "?"),
    }


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trinity Model Selector")
    parser.add_argument("task", help="Task description")
    parser.add_argument("--type", dest="task_type", default=None)
    parser.add_argument("--agent", default=None)
    parser.add_argument("--force", default=None)
    parser.add_argument("--pool", default=None, help="Path to model pool JSON")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    
    result = select_model(
        task=args.task,
        task_type=args.task_type,
        agent=args.agent,
        force_model=args.force,
        pool_path=args.pool,
        debug=args.debug,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
