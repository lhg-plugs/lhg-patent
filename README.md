<!-- About 简介（推送后填写到仓库 About 栏）：
专利撰写助手：交底书→权利要求书→说明书→新创性自检 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-patent
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, patent, intellectual-property, claims -->

# lhg-patent：专利撰写助手，交底书到新创性自检一条龙

> ⚠️ **合规声明（首屏置顶）**：本插件产出的是**专利撰写辅助草稿**，**不能直接提交专利申请**，**必须经专利代理人/代理机构复核**后方可使用；现有技术检索结果**不保证查全**，新颖性/创造性的最终判断请专利代理人做出。
>
> **一句话介绍**：给 AI 编程助手装上"专利撰写助手"——交底书挖掘 → 权利要求书撰写 → 说明书组织 → 新创性自检一条龙；**11 条确定性审计规则专抓引用断裂与标记不一致，合规提醒全程护航**。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-patent
> /plugin install lhg-patent@lhg-plugs
> ```

## 它是什么

`lhg-patent` 是一个 Claude Code 插件（plugin 为主、skill 为辅）：

- **3 个命令**（小白入口）：`patent` 专利撰写一条龙（交底书→权利要求书→说明书→新创性自检），`claims` 权利要求书专项（独立/从属撰写与引用检查），`prior-art` 现有技术检索指引（检索式构造+诚实声明）
- **3 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：`disclosure` 交底书挖掘（技术特征拆解+问题-手段-效果三要素）、`claims-draft` 权利要求撰写规范（上位概括+引用关系+说明书组织）、`novelty-check` 新颖性/创造性/实用性三性自检清单
- **3 个专家 agent**：交底书挖掘专家、权利要求撰写专家、新创性审查专家
- **2 个硬门 hook**：commit 前跑专利审计（有 blocker 拦截，可一键关闭）；写专利文档无合规声明时提醒补上
- **11 条确定性审计规则**（`patent_audit.py`，纯 Python 标准库、零第三方依赖）：权利要求引用断裂/自引用拦截；附图标记不一致拦截；术语前后不一致/保护范围过窄/必要特征缺失/三性清单缺失预警

## 合规设计

1. **声明置顶**：README 首屏、每个 SKILL.md 开头、每条命令输出末尾，都有显著的合规声明。
2. **写入提醒**：hook 在专利文档写入后检查合规声明，缺失即提醒（不拦截，exit 0）；`LHG_PATENT_HOOKS_OFF=1` 可关闭。
3. **审计兜底**：`patent_audit.py` 的 PAT-CLM-001/002（引用断裂）与 PAT-DSC-001（附图标记断裂）是 blocker，`patent` 命令逐条清零。
4. **措辞红线**：检索结论只许写"本次检索未发现"，不许写"查全了""没有现有技术"；三性只写依据不写结论词。

## 3 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-patent:patent` | 专利撰写一条龙：交底书→权利要求书→说明书→新创性自检 | `/lhg-patent:patent "一种带水温显示的智能水杯"` |
| `/lhg-patent:claims` | 权利要求书专项：保护策略→独立/从属撰写→引用检查 | `/lhg-patent:claims ./disclosure.md` |
| `/lhg-patent:prior-art` | 现有技术检索指引：检索式→检索源→比对表→诚实声明 | `/lhg-patent:prior-art "智能水杯 水温显示"` |

## 目录结构

```
lhg-patent/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 3 个命令：patent / claims / prior-art
├── skills/                  # 3 个平台中立 skill（disclosure / claims-draft / novelty-check，合规声明置顶）
├── agents/                  # 3 个专家 agent（miner / drafter / reviewer）
├── hooks/                   # commit 审计硬门 + 合规声明提醒（fail-open，可一键关闭）
├── scripts/audit/           # patent_audit.py（11 条规则，零第三方依赖）
├── fixtures/                # 好/坏对照用例（bad/good）
├── smoke_test.py            # 冒烟测试（52 项，含合规声明检查）
├── ATTRIBUTION.md           # 灵感来源声明
└── LICENSE                  # MIT
```

## 什么时候用 / 什么时候不用（FAQ）

**Q：它写出来的专利文件能直接提交申请吗？**
A：**不能**，这是本插件的红线。所有产出都是撰写辅助草稿，必须经专利代理人/代理机构复核后才能用于申请。专利申请涉及严格的法律格式与程序要求，AI 草稿只是帮你把前期工作做扎实。

**Q：它能替代专利代理人吗？**
A：不能。它做的是代理人**之前**的工作：把你的想法挖清楚（交底书）、把初稿写规矩（权利要求书/说明书）、把明显硬伤先拦下来（审计）。三性判断、答辩策略、程序性事务必须找持证代理人。

**Q：检索功能能保证查全现有技术吗？**
A：不能。`prior-art` 命令给你的是系统的检索方法（检索式构造、检索源清单、比对表），但任何检索都不保证查全。结论一律写"本次检索未发现"，不写"没有现有技术"。

**Q：我是个人发明人，没接触过专利，能用吗？**
A：能。`disclosure` skill 就是为你准备的：它会像专利代理人一样访谈你，问出技术特征、三要素、必要特征，输出一份代理人愿意接的交底书。

**Q：一定要用 Claude Code 吗？**
A：`skills/` 下的方法论是平台中立的纯 Markdown，可直接搬到豆包、Workbuddy 等 agent 平台用。只有 commands/agents/hooks 需要 Claude Code。

**Q：hook 把我的 commit 拦了怎么办？**
A：两种处理：① 按审计报告修掉 blocker（引用断裂这类硬伤，修了对你有好处）；② 紧急情况 `export LHG_PATENT_HOOKS_OFF=1` 单次豁免。

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（JSON 合法、skill/command/agent 完整性、合规声明置顶、11 条审计规则、fixtures 埋点命中、hooks 行为）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-patent/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。**注意：提 issue 时不要公开你的技术细节**（公开可能影响新颖性）。

## lhg-plugs 插件矩阵

| 插件 | 一句话 | 安装 |
|---|---|---|
| [lhg-fullstack](https://github.com/lhg-plugs/lhg-fullstack) | 小白一句话 → 高质量全栈应用 | `/plugin install lhg-fullstack@lhg-plugs` |
| [lhg-experiment](https://github.com/lhg-plugs/lhg-experiment) | 实验设计专家：假设→设计→功效测算→结果解读一条龙 | `/plugin install lhg-experiment@lhg-plugs` |
| [lhg-patent](https://github.com/lhg-plugs/lhg-patent) | 专利撰写助手：交底书→权利要求书→说明书→新创性自检 | `/plugin install lhg-patent@lhg-plugs` |

> 完整矩阵见 [lhg-plugs/marketplace](https://github.com/lhg-plugs/marketplace)。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 抖音：搜「刘老师讲AI实战」
- 微信：lhgsmsw
