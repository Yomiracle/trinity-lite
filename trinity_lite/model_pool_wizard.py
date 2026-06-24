#!/usr/bin/env python3
"""
Interactive model pool setup wizard for Trinity.
No JSON knowledge required — asks questions, generates config.
"""

import json
import os
import sys
from pathlib import Path

TIERS = {
    "1": ("budget", "便宜够用 — 简单任务、日常开发"),
    "2": ("standard", "标准能力 — 大多数编程任务"),
    "3": ("premium", "最强推理 — 架构设计、安全审计"),
}

AGENTS = {
    "1": "codex",
    "2": "claude_code",
}

STRENGTH_OPTIONS = [
    ("coding", "写代码/改bug"),
    ("code_review", "审查代码"),
    ("reasoning", "深度推理"),
    ("architecture", "架构设计"),
    ("security", "安全审计"),
    ("diagnosis", "故障诊断"),
    ("chinese", "中文能力"),
    ("general", "通用对话"),
    ("fast", "速度快"),
    ("creative", "创意生成"),
]

OUTPUT_PATHS = [
    Path.home() / ".trinity" / "model_pool.json",
    Path("model_pool.json"),
]


def ask(prompt: str, default: str = "") -> str:
    if default:
        result = input(f"  {prompt} [{default}]: ").strip()
        return result or default
    return input(f"  {prompt}: ").strip()


def pick_option(prompt: str, options: dict, default: str = None) -> str:
    print(f"\n  {prompt}")
    for key, (value, desc) in options.items():
        marker = " ←" if key == default else ""
        print(f"    {key}) {value} — {desc}{marker}")
    while True:
        choice = ask("选一个", default or "")
        if choice in options:
            return options[choice][0]
        print(f"    请输入 {'/'.join(options.keys())}")


def pick_multi(prompt: str, options: list) -> list:
    print(f"\n  {prompt}")
    for i, (value, desc) in enumerate(options, 1):
        print(f"    {i}) {value} ({desc})")
    print(f"    输入数字，多个用逗号分隔，如 1,3,5")
    while True:
        try:
            raw = ask("选哪些", "")
            indices = [int(x.strip()) for x in raw.split(",") if x.strip()]
            result = [options[i-1][0] for i in indices if 1 <= i <= len(options)]
            if result:
                return result
            print("    请至少选一个")
        except (ValueError, IndexError):
            print("    格式不对，比如输入 1,3,5")


def pick_agents(prompt: str) -> list:
    print(f"\n  {prompt}")
    print(f"    1) codex — OpenAI Codex (主工程师)")
    print(f"    2) claude_code — Claude Code (审查员)")
    print(f"    3) hermes — Hermes (编排者)")
    print(f"    输入数字或数字组合，如 2 或 1,3")
    while True:
        raw = ask("哪些 Agent 能用这个模型", "1,2,3")
        parts = [x.strip() for x in raw.split(",")]
        result = []
        for p in parts:
            if p in AGENTS:
                result.append(AGENTS[p])
        if result:
            return result
        print("    请输入 1, 2, 3 的组合")


def guess_api_type(name: str) -> str:
    name_lower = name.lower()
    if any(x in name_lower for x in ["gpt", "openai", "o1", "o3", "o4"]):
        return "openai"
    if any(x in name_lower for x in ["claude", "anthropic", "sonnet", "opus", "haiku"]):
        return "anthropic"
    if any(x in name_lower for x in ["glm", "chatglm", "zhipu"]):
        return "anthropic"
    if any(x in name_lower for x in ["deepseek"]):
        return "anthropic"
    if any(x in name_lower for x in ["gemini", "google"]):
        return "google"
    return "openai_compatible"


def main():
    print()
    print("═" * 56)
    print("  Trinity 模型池配置向导")
    print("  回答几个问题, 自动生成 model_pool.json")
    print("═" * 56)
    
    # Step 1: How many models?
    print()
    count = int(ask("你有几个模型可以用?", "2"))
    print(f"  好的, 我们来配置 {count} 个模型。")
    
    pool = {}
    
    for i in range(1, count + 1):
        print()
        print(f"  ── 模型 {i}/{count} ──")
        
        name = ask("模型名称 (如 glm-5.2, gpt-5.5)", f"model-{i}")
        tier = pick_option("这个模型的能力等级?", {
            "1": ("budget", "便宜够用 — 简单任务"),
            "2": ("standard", "标准能力 — 大多数编程任务"),
            "3": ("premium", "最强推理 — 架构设计、安全审计"),
        }, default="1")
        
        strengths = pick_multi("这个模型擅长什么?", STRENGTH_OPTIONS)
        agents = pick_agents("哪些 Agent 能用这个模型?")
        
        cost = ask("API 价格 (如 $1.4/$4.4 per 1M, 免费填 free)", "free")
        api_type = guess_api_type(name)
        api_type = ask("API 类型 (openai/anthropic/google)", api_type)
        
        pool[name] = {
            "tier": tier,
            "strengths": strengths,
            "available_to": agents,
            "cost": cost,
            "api_type": api_type,
        }
        
        print(f"  ✓ {name} 已添加")
    
    # Step 2: Save
    print()
    print("═" * 56)
    print("  配置预览:")
    print(json.dumps(pool, ensure_ascii=False, indent=2))
    print("═" * 56)
    
    # Pick save location
    print()
    print("  保存到哪里?")
    for i, p in enumerate(OUTPUT_PATHS[:2], 1):
        print(f"    {i}) {p}")
    print(f"    3) 当前目录")
    print(f"    4) 自定义路径")
    
    choice = ask("选一个", "1")
    if choice == "2":
        save_path = OUTPUT_PATHS[1]
    elif choice == "3":
        save_path = Path("model_pool.json")
    elif choice == "4":
        save_path = Path(ask("输入路径", str(OUTPUT_PATHS[0])))
    else:
        save_path = OUTPUT_PATHS[0]
    
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"  ✅ 已保存到 {save_path}")
    print(f"  💡 设置环境变量: export TRINITY_MODEL_POOL={save_path}")
    print(f"  💡 或放到 ~/.hermes/model_pool.json 自动加载")
    print()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\n  已取消。")
        sys.exit(0)
