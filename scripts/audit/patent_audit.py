#!/usr/bin/env python3
"""lhg-patent 确定性专利审计：11 条规则，零第三方依赖。

扫描目标目录：
  - *claim*/*权利要求*.txt|md —— 权利要求书（引用关系/结构/保护范围）
  - *desc*/*说明*/*description*.md|txt —— 说明书（附图标记/术语一致性/结构）
  - *novelty*/*三性*.json —— 新创性自检清单

输出 JSON 与人类可读报告；有 blocker 时以 exit code 2 退出（供 hooks 与 CI 使用）。

用法：
    python3 patent_audit.py --target <目录> [--format json|text] [--fail-on blocker|warning|nit]

规则文案均为本插件原创（专利撰写规范为公开的行业常识）。
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"
TOOL = "lhg-patent/audit"

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".next",
             "vendor", "coverage", ".turbo", "out"}

CLAIM_FILE_RE = re.compile(r"claim|权利要求", re.I)
DESC_FILE_RE = re.compile(r"desc|说明|description", re.I)
NOVELTY_FILE_RE = re.compile(r"novelty|三性", re.I)

CLAIM_HEAD_RE = re.compile(r"^权利要求\s*(\d+)\s*$")
CITE_RE = re.compile(r"权利要求\s*(\d+)")
FEATURE_MARK_RE = re.compile(r"其特征在于|特征在于")
MARK_DEF_RE = re.compile(r"(?<!\d)(\d{2,4})[、，,]\s*[一-鿿]")
MARK_REF_RE = re.compile(r"（(\d{2,4})）")
SYNONYM_PAIRS = [
    ("连接件", "连接部件"),
    ("固定部", "固定部件"),
    ("驱动装置", "驱动机构"),
    ("容纳腔", "容置腔"),
    ("显示屏", "显示器"),
    ("锁止机构", "锁定机构"),
]
STRUCT_SECTIONS = ["技术领域", "背景技术", "发明内容"]


class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file", "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line, snippet, detail):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet
        self.detail = detail

    def to_dict(self):
        return {
            "rule_id": self.rule_id, "severity": self.severity,
            "category": self.category, "title": self.title,
            "file": self.file, "line": self.line,
            "snippet": self.snippet, "detail": self.detail,
        }


RULES = []
_RULE_BY_ID = {}


def rule(rule_id, severity, category, title, detail):
    def deco(fn):
        r = {"id": rule_id, "severity": severity, "category": category,
             "title": title, "detail": detail}
        _RULE_BY_ID[rule_id] = r
        r["check"] = fn
        RULES.append(r)
        return fn
    return deco


def _mk(rule_id, file, line, snippet):
    r = _RULE_BY_ID[rule_id]
    return Finding(r["id"], r["severity"], r["category"], r["title"],
                   file, line, snippet[:160], r["detail"])


def _collect(target, name_re, exts):
    out = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            _, ext = os.path.splitext(f)
            if ext.lower() in exts and name_re.search(f):
                out.append(os.path.join(root, f))
    return sorted(out)


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def parse_claims(text):
    """解析权利要求书 -> [(num, header_line_no, body_text)]。"""
    lines = text.split("\n")
    claims, cur = [], None
    for i, ln in enumerate(lines):
        m = CLAIM_HEAD_RE.match(ln.strip())
        if m:
            if cur:
                claims.append(cur)
            cur = {"num": int(m.group(1)), "line": i + 1, "body": []}
        elif cur:
            cur["body"].append(ln)
    if cur:
        claims.append(cur)
    return [(c["num"], c["line"], "\n".join(c["body"]).strip()) for c in claims]


def _claim_files(target):
    for p in _collect(target, CLAIM_FILE_RE, {".txt", ".md"}):
        yield os.path.relpath(p, target), _read(p)


def _desc_files(target):
    for p in _collect(target, DESC_FILE_RE, {".txt", ".md"}):
        yield os.path.relpath(p, target), _read(p)


@rule("PAT-CLM-001", "blocker", "引用关系", "引用了不存在的权利要求编号",
      "从属权利要求引用了不存在的编号。引用断裂的权利要求书会被审查员直接驳回，"
      "提交前必须修好编号。")
def r_clm_001(target, ctx):
    out = []
    for rel, text in _claim_files(target):
        claims = parse_claims(text)
        nums = {n for n, _, _ in claims}
        for n, line, body in claims:
            for m in CITE_RE.finditer(body):
                ref = int(m.group(1))
                if ref not in nums:
                    out.append(_mk("PAT-CLM-001", rel, line,
                                   "权利要求%d 引用了不存在的权利要求%d" % (n, ref)))
                    break
    return out


@rule("PAT-CLM-002", "blocker", "引用关系", "引用自身或后续编号",
      "权利要求引用了自身或编号更大的权利要求。从属权利要求只能引用在它之前的"
      "权利要求，反向引用在逻辑上不成立。")
def r_clm_002(target, ctx):
    out = []
    for rel, text in _claim_files(target):
        for n, line, body in parse_claims(text):
            for m in CITE_RE.finditer(body):
                ref = int(m.group(1))
                if ref >= n:
                    out.append(_mk("PAT-CLM-002", rel, line,
                                   "权利要求%d 引用了权利要求%d（自身或后续）" % (n, ref)))
                    break
    return out


@rule("PAT-CLM-003", "warning", "撰写规范", "独立权利要求缺少特征部分标志",
      "独立权利要求（不引用其他权利要求的）没有「其特征在于」类表述，"
      "前序部分与特征部分界限不清。建议按「前序（已知技术）+ 其特征在于 + 特征部分（发明点）」改写。")
def r_clm_003(target, ctx):
    out = []
    for rel, text in _claim_files(target):
        for n, line, body in parse_claims(text):
            is_independent = not CITE_RE.search(body)
            if is_independent and body and not FEATURE_MARK_RE.search(body):
                out.append(_mk("PAT-CLM-003", rel, line,
                               "权利要求%d 为独立权利要求但无「其特征在于」" % n))
    return out


@rule("PAT-CLM-004", "warning", "保护范围", "保护范围过窄预警",
      "独立权利要求中限定词（「所述」/「其中」）过多，保护范围可能被过度限缩。"
      "独立权利要求只写必要技术特征，细节下沉到从属权利要求形成梯度保护。")
def r_clm_004(target, ctx):
    out = []
    for rel, text in _claim_files(target):
        for n, line, body in parse_claims(text):
            if not CITE_RE.search(body) and body:
                hits = len(re.findall(r"所述|其中", body))
                if hits >= 10:
                    out.append(_mk("PAT-CLM-004", rel, line,
                                   "权利要求%d 限定词出现 %d 次，保护范围疑似过窄" % (n, hits)))
    return out


@rule("PAT-CLM-005", "warning", "保护范围", "必要技术特征缺失",
      "features.json 中声明的必要技术特征没有出现在权利要求书中。"
      "必要技术特征是解决技术问题的最小特征集合，缺失会导致保护不完整。")
def r_clm_005(target, ctx):
    out = []
    feat_files = _collect(target, re.compile(r"features", re.I), {".json"})
    if not feat_files:
        return []
    try:
        feats = json.loads(_read(feat_files[0])).get("essential_features", [])
    except Exception:
        return []
    for rel, text in _claim_files(target):
        for feat in feats:
            if feat and feat not in text:
                out.append(_mk("PAT-CLM-005", rel, 0,
                               "必要技术特征「%s」未出现在权利要求书中" % feat))
    return out


@rule("PAT-CLM-006", "nit", "撰写规范", "权利要求末尾标点不规范",
      "权利要求段落末尾不是中文句号「。」。每条权利要求自成一段、以句号结尾是基本格式要求。")
def r_clm_006(target, ctx):
    out = []
    for rel, text in _claim_files(target):
        for n, line, body in parse_claims(text):
            body = body.strip()
            if body and not body.endswith("。"):
                out.append(_mk("PAT-CLM-006", rel, line,
                               "权利要求%d 末尾不是句号" % n))
    return out


def _defined_marks(text):
    sec = re.search(r"附图说明(.+?)(##|具体实施方式|\Z)", text, re.S)
    scope = sec.group(1) if sec else text
    return {m.group(1) for m in MARK_DEF_RE.finditer(scope)}


@rule("PAT-DSC-001", "blocker", "附图标记", "附图标记与附图说明不一致",
      "正文中引用的附图标记（如「杯体（10）」）没有在「附图说明」中定义。"
      "标记断裂会导致说明书公开不充分，影响授权。")
def r_dsc_001(target, ctx):
    out = []
    for rel, text in _desc_files(target):
        defined = _defined_marks(text)
        if not defined:
            continue
        seen = set()
        for m in MARK_REF_RE.finditer(text):
            mark = m.group(1)
            if mark not in defined and mark not in seen:
                seen.add(mark)
                out.append(_mk("PAT-DSC-001", rel, text[:m.start()].count("\n") + 1,
                               "附图标记（%s）在附图说明中未定义" % mark))
    return out


@rule("PAT-DSC-002", "warning", "术语一致", "术语前后不一致",
      "同一技术特征用了两种不同表述。术语不一致会被审查员质疑为不清楚，"
      "全文统一为一种表述。")
def r_dsc_002(target, ctx):
    out = []
    for rel, text in _desc_files(target):
        for a, b in SYNONYM_PAIRS:
            if a in text and b in text:
                out.append(_mk("PAT-DSC-002", rel, 0,
                               "「%s」与「%s」并存，请统一术语" % (a, b)))
    return out


@rule("PAT-DSC-003", "warning", "说明书结构", "缺少具体实施方式",
      "说明书没有「具体实施方式」/「实施例」段落。实施例是证明「能够实现」的关键，"
      "缺失会导致公开不充分驳回风险。")
def r_dsc_003(target, ctx):
    out = []
    for rel, text in _desc_files(target):
        if "具体实施方式" not in text and "实施例" not in text:
            out.append(_mk("PAT-DSC-003", rel, 0, "缺少具体实施方式/实施例"))
    return out


@rule("PAT-DSC-004", "warning", "说明书结构", "缺少三段式结构",
      "说明书缺少「技术领域/背景技术/发明内容」中的两项以上。"
      "完整的三段式是审查员快速理解发明的基础框架。")
def r_dsc_004(target, ctx):
    out = []
    for rel, text in _desc_files(target):
        missing = [s for s in STRUCT_SECTIONS if s not in text]
        if len(missing) >= 2:
            out.append(_mk("PAT-DSC-004", rel, 0,
                           "缺少：%s" % "、".join(missing)))
    return out


@rule("PAT-NOV-001", "warning", "新创性", "三性自检清单缺失",
      "未找到 *novelty*.json（三性自检清单）。提交前至少自问三遍："
      "新颖性（现有技术里有没有）、创造性（本领域技术人员是否容易想到）、"
      "实用性（能不能制造/使用）。")
def r_nov_001(target, ctx):
    files = _collect(target, NOVELTY_FILE_RE, {".json"})
    if not files:
        return [_mk("PAT-NOV-001", ".", 0, "未找到 *novelty*.json")]
    out = []
    for p in files:
        rel = os.path.relpath(p, target)
        try:
            d = json.loads(_read(p))
        except Exception:
            out.append(_mk("PAT-NOV-001", rel, 0, "novelty.json 解析失败"))
            continue
        for key in ("新颖性", "创造性", "实用性"):
            if not d.get(key):
                out.append(_mk("PAT-NOV-001", rel, 0, "三性自检缺少「%s」项" % key))
    return out


def run(target):
    findings = []
    for r in RULES:
        try:
            for f in r["check"](target, {}) or []:
                findings.append(f)
        except Exception:
            continue
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description="lhg-patent 确定性专利审计")
    ap.add_argument("--target", default=".", help="扫描目录")
    ap.add_argument("--format", choices=["json", "text"], default="text")
    ap.add_argument("--fail-on", choices=["blocker", "warning", "nit"], default="blocker")
    args = ap.parse_args(argv)

    target = os.path.abspath(args.target)
    if not os.path.isdir(target):
        print("target 不是目录：%s" % args.target, file=sys.stderr)
        return 1

    findings = run(target)
    sev_rank = {"blocker": 3, "warning": 2, "nit": 1}
    counts = {"blocker": 0, "warning": 0, "nit": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    files = (_collect(target, CLAIM_FILE_RE, {".txt", ".md"})
             + _collect(target, DESC_FILE_RE, {".txt", ".md"})
             + _collect(target, NOVELTY_FILE_RE, {".json"}))
    result = {
        "tool": TOOL,
        "version": VERSION,
        "target": args.target,
        "summary": {
            "files_scanned": len(files),
            "rules_run": len(RULES),
            "blocker": counts["blocker"],
            "warning": counts["warning"],
            "nit": counts["nit"],
        },
        "findings": [f.to_dict() for f in sorted(
            findings, key=lambda x: (-sev_rank.get(x.severity, 0), x.file, x.line))],
    }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        s = result["summary"]
        print("专利审计：扫描 %d 文件，运行 %d 条规则" % (s["files_scanned"], s["rules_run"]))
        print("blocker=%d warning=%d nit=%d" % (s["blocker"], s["warning"], s["nit"]))
        for f in result["findings"]:
            print("[%s][%s] %s:%d %s" % (
                f["severity"].upper(), f["rule_id"], f["file"], f["line"], f["title"]))
            print("    %s" % f["detail"])
            if f["snippet"]:
                print("    → %s" % f["snippet"])

    level = sev_rank[args.fail_on]
    bad = any(sev_rank.get(f.severity, 0) >= level for f in findings)
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
