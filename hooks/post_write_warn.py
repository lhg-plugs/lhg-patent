#!/usr/bin/env python3
"""lhg-patent 硬门②（警告级，不拦截）：写入权利要求书/说明书类文档时，
提醒"须经专利代理人复核后方可用于申请"（合规提醒）。

触发：PostToolUse / Write|Edit。只做提醒，永远 exit 0、不拦截写入。

逃生方式：LHG_PATENT_HOOKS_OFF=1（环境变量）可关闭本提醒；
或 /plugin disable lhg-patent 停用整个插件。
零第三方依赖。
"""

import json
import os
import re
import sys

PATENT_NAME_RE = re.compile(r"claim|权利要求|desc|说明|description|patent|专利", re.I)
REVIEWED_RE = re.compile(r"专利代理人.*复核|经.*复核后方可")


def main() -> int:
    if os.environ.get("LHG_PATENT_HOOKS_OFF") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # fail-open

    tool_input = payload.get("tool_input", {}) or {}
    path = tool_input.get("file_path", "") or ""
    base = os.path.basename(path)
    if not PATENT_NAME_RE.search(base):
        return 0  # 非专利文档：快速放行
    if not os.path.isfile(path):
        return 0

    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return 0

    if not REVIEWED_RE.search(text):
        note = (
            "lhg-patent 合规提醒：这份专利文档里没有「须经专利代理人复核」声明。\n"
            "AI 生成的专利文本不能直接提交申请，必须经专利代理人/代理机构复核后方可使用；"
            "检索结果不保证查全。建议在文档末尾补上合规声明。\n"
            "关闭此提醒：LHG_PATENT_HOOKS_OFF=1"
        )
        sys.stdout.write(json.dumps({"additionalContext": note}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
