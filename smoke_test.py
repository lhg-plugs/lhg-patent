#!/usr/bin/env python3
"""lhg-patent 插件冒烟测试：全部绿才算过。

检查项：
 1. 三个 JSON 合法（plugin.json / marketplace.json / hooks.json）
 2. 3 个 SKILL.md 都有 name/description frontmatter，且 150~320 行
 3. 3 个 commands 都有 description frontmatter
 4. 3 个 agents 都有 name/description/tools/model frontmatter
 5. skills 平台中立：不含 Claude Code 专有工具名
 6. 合规声明：README 首屏 + 主 skill（disclosure）开头有合规声明
 7. patent_audit.py：坏 fixture 埋点全命中且 exit!=0；好 fixture 零 blocker 且 exit==0
 8. hooks 脚本：commit 拦截 / 非 commit 放行 / 逃生开关 / 写专利文档合规提醒

用法：python3 smoke_test.py [--repo <插件根目录>]
退出码：0=全绿，1=有失败。
"""

import argparse
import json
import os
import re
import subprocess
import sys

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((PASS if cond else FAIL, name, detail))
    return cond


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def frontmatter(path):
    text = read(path)
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = {}
    for ln in text[3:end].split("\n"):
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", ln)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)


# 坏 fixture 必须全部命中的规则
BAD_MUST = {
    "PAT-CLM-001", "PAT-CLM-002", "PAT-CLM-003", "PAT-CLM-004",
    "PAT-CLM-005", "PAT-CLM-006",
    "PAT-DSC-001", "PAT-DSC-002", "PAT-DSC-003", "PAT-DSC-004",
    "PAT-NOV-001",
}
NEUTRAL_DENY = ["Task tool", "Bash tool", "Edit tool", "Write tool", "Read tool",
                "AskUserQuestion", "subagent_type", "PreToolUse", "PostToolUse",
                "${CLAUDE_", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR"]
COMPLY_KEYS = ["专利代理人", "不能直接提交"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    AUDIT = os.path.join(repo, "scripts", "audit")

    # 1. JSON 合法
    for rel in [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                "hooks/hooks.json"]:
        p = os.path.join(repo, rel)
        try:
            d = json.loads(read(p))
            check("JSON 合法: " + rel, True)
            if rel.endswith("plugin.json"):
                check("plugin.json name==lhg-patent",
                      d.get("name") == "lhg-patent", str(d.get("name")))
                check("plugin.json 有 version/description/author",
                      all(d.get(k) for k in ("version", "description", "author")))
            if rel.endswith("marketplace.json"):
                ps = d.get("plugins", [])
                check("marketplace.json source==./ 且 name 一致",
                      len(ps) == 1 and ps[0].get("source") == "./" and
                      ps[0].get("name") == "lhg-patent", str(ps))
            if rel.endswith("hooks.json"):
                check("hooks.json 顶层有 hooks 包装", "hooks" in d)
                evts = d["hooks"]
                check("hooks.json 有 PreToolUse+PostToolUse",
                      "PreToolUse" in evts and "PostToolUse" in evts, str(list(evts)))
        except Exception as e:
            check("JSON 合法: " + rel, False, str(e))

    # 2. SKILL.md
    for skill in ["disclosure", "claims-draft", "novelty-check"]:
        p = os.path.join(repo, "skills", skill, "SKILL.md")
        fm = frontmatter(p)
        check("skill frontmatter: " + skill,
              bool(fm.get("name")) and bool(fm.get("description")),
              "name=%s" % fm.get("name"))
        nlines = len(read(p).split("\n"))
        check("skill 行数 150~320: %s (%d 行)" % (skill, nlines), 150 <= nlines <= 320, str(nlines))
        body = read(p)
        bad_words = [w for w in NEUTRAL_DENY if w in body]
        check("skill 平台中立: " + skill, not bad_words, "命中: %s" % bad_words)
        check("skill 有出品区: " + skill, "出品：刘洪光" in body and "https://github.com/lhg-skills" in body)
        check("skill 有自检与反馈: " + skill, "自检与反馈" in body)
        check("skill 有合规声明: " + skill,
              all(k in body for k in COMPLY_KEYS), "缺合规关键词")

    # 3. commands
    for cmd in ["patent", "claims", "prior-art"]:
        p = os.path.join(repo, "commands", cmd + ".md")
        fm = frontmatter(p)
        check("command description: " + cmd, bool(fm.get("description")), str(fm.get("description"))[:60])
        check("command 有 argument-hint: " + cmd, bool(fm.get("argument-hint")))

    # 4. agents
    for ag in ["disclosure-miner", "claims-drafter", "novelty-reviewer"]:
        p = os.path.join(repo, "agents", ag + ".md")
        fm = frontmatter(p)
        check("agent frontmatter: " + ag,
              all(fm.get(k) for k in ("name", "description", "tools", "model")),
              str({k: fm.get(k) for k in ("name", "model")}))

    # 5. 合规声明置顶：README 首屏 + disclosure 开头
    readme = read(os.path.join(repo, "README.md"))
    check("README 首屏合规声明",
          all(k in readme[:1500] for k in COMPLY_KEYS), "首屏缺合规声明")
    disc = read(os.path.join(repo, "skills", "disclosure", "SKILL.md"))
    check("disclosure 开头合规声明",
          all(k in disc[:1200] for k in COMPLY_KEYS), "开头缺合规声明")

    # 6. patent_audit.py 冒烟
    def audit_hits(target):
        r = run([sys.executable, os.path.join(AUDIT, "patent_audit.py"),
                 "--target", os.path.join(repo, target), "--format", "json"])
        try:
            d = json.loads(r.stdout)
        except Exception:
            return None, r.returncode, []
        return d["summary"], r.returncode, [f["rule_id"] for f in d["findings"]]

    s, code, ids = audit_hits("fixtures/bad")
    check("audit 坏 fixture exit!=0", code != 0, "exit=%d" % code)
    check("audit 坏 fixture blocker>0", s and s["blocker"] > 0, str(s))
    missing = BAD_MUST - set(ids)
    check("audit 埋点全命中 (%d/%d)" % (len(BAD_MUST - missing), len(BAD_MUST)),
          not missing, "缺失: %s" % sorted(missing))
    check("audit 规则数>=10 (%s)" % (s and s["rules_run"]),
          s and s["rules_run"] >= 10, str(s))

    s, code, ids = audit_hits("fixtures/good")
    check("audit 好 fixture 零 blocker", s and s["blocker"] == 0, str(s))
    check("audit 好 fixture exit==0", code == 0, "exit=%d" % code)

    # 7. hooks 脚本
    def hook(script, payload, env=None):
        e = dict(os.environ); e.update(env or {})
        return run([sys.executable, os.path.join(repo, "hooks", script)],
                   input=payload, env=e)

    r = hook("pre_commit_audit.py", '{"tool_input":{"command":"git status"}}')
    check("hook: 非 commit 放行", r.returncode == 0 and not r.stdout.strip())
    r = hook("pre_commit_audit.py",
             '{"tool_input":{"command":"git commit -m \\"x\\""}}',
             {"CLAUDE_PROJECT_DIR": os.path.join(repo, "fixtures/bad")})
    try:
        d = json.loads(r.stdout)
        denied = d["hookSpecificOutput"]["permissionDecision"] == "deny"
    except Exception:
        denied = False
    check("hook: commit 有 blocker 拦截", denied, r.stdout[:120])
    r = hook("pre_commit_audit.py",
             '{"tool_input":{"command":"git commit -m \\"x\\""}}',
             {"CLAUDE_PROJECT_DIR": os.path.join(repo, "fixtures/bad"),
              "LHG_PATENT_HOOKS_OFF": "1"})
    check("hook: 逃生开关生效", r.returncode == 0 and not r.stdout.strip())

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        no_decl = os.path.join(td, "claims.txt")
        with open(no_decl, "w") as f:
            f.write("权利要求1\n一种智能水杯。\n")
        r = hook("post_write_warn.py", json.dumps({"tool_input": {"file_path": no_decl}}))
        check("hook: 专利文档无合规声明 → 提醒", "additionalContext" in r.stdout, r.stdout[:80])
        with open(no_decl, "w") as f:
            f.write("权利要求1\n一种智能水杯。\n须经专利代理人复核后方可用于申请。\n")
        r = hook("post_write_warn.py", json.dumps({"tool_input": {"file_path": no_decl}}))
        check("hook: 专利文档有合规声明 → 不提醒", not r.stdout.strip())
        other = os.path.join(td, "notes.txt")
        with open(other, "w") as f:
            f.write("随便写点\n")
        r = hook("post_write_warn.py", json.dumps({"tool_input": {"file_path": other}}))
        check("hook: 非专利文档 → 不提醒", not r.stdout.strip())

    # 报告
    print("=" * 60)
    print("lhg-patent 冒烟测试报告")
    print("=" * 60)
    fails = 0
    for st, name, detail in results:
        mark = "✓" if st == PASS else "✗"
        print("%s %s %s" % (mark, st, name))
        if detail and st == FAIL:
            print("    → %s" % detail)
        if st == FAIL:
            fails += 1
    print("=" * 60)
    print("共 %d 项，通过 %d，失败 %d" % (len(results), len(results) - fails, fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
