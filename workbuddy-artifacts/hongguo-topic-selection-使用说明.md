# 如何使用这个 Gemini Skill（hongguo-topic-selection）

一个可移植的「红果短剧选题专家」Skill，把一句话需求变成可立项的选题方案。

## 它解决什么问题

**「下一部拍什么、能不能火、能不能回本、会不会踩线」** —— 短剧立项前的选题决策：
赛道扫描 → 爆款拆解 → 人设/钩子 → 剧名封面 → 成本保本 → 合规预检。

## 目录结构

```
hongguo-topic-selection/
├── SKILL.md                 # 核心：人设 + 12 层能力 + 10 步工作流 + 速查 + 质量门 + 安全边界
└── references/              # 深度细节（按需读取）
    ├── tracks.md            # 男频/女频 20 赛道、生命周期、拥挤度、人群
    ├── teardown.md          # 四层拆解字段、迁移与失效条件、人设/反派/配角
    ├── hooks-pacing.md      # 前三秒/60秒节拍、集尾五收法、冲突阶梯、情绪曲线
    ├── title-cover.md       # 命名八法、封面三要素、点开率诊断
    ├── cost-finance.md      # 成本分级、周期倒排、保本反推、三情景、追投止损
    └── compliance.md        # 三重预检、各题材表达边界、版权授权、免责口径
```

## 方式 A：Gemini 网页 / App（推荐给聊天用）

1. 打开 gemini.google.com → **设置 → 技能（Skills）→ 上传 / 创建**。
2. 上传 `SKILL.md`。
3. 把 `references/` 里的 6 个 md 文件作为**附件/参考文件**一并上传（"Add files when uploading a skill.md file"），让 Gemini 每次都能引用。
4. 在对话里输入 `/hongguo-topic-selection` 或直接描述需求，Gemini 会自动触发。

> 注意：Gemini App 的 Skill 是聊天型，不会读你本机其它文件；所以知识点要么写进 SKILL.md，要么作为附件上传。这里已经把核心方法写进 SKILL.md，references 只是补充深度。

## 方式 B：Gemini CLI（读本机文件）

把整个 `hongguo-topic-selection/` 文件夹放到：

```
~/.gemini/skills/hongguo-topic-selection/
```

CLI 会自动发现，并按 `SKILL.md` 里的说明按需读取 `references/`。

## 已知边界

- 资源口径为 **2026-09**；涉及平台分账、榜单、审核尺度时，本 Skill 会提示「须以平台当期公告与后台数据复核」，不会编造条文。
- 不写剧本正文（可给分集梗概 / 结构表 / 人设包作为编剧交接件）；不承诺播放量与收益，只给区间与条件。
- 涉及版权、授权与合规的最终结论须由法务确认。

## 来源

由 WorkBuddy 专家「红果短剧选题专家（Short Drama Topic Master）」的克隆包 `my-hongguo-topic-expert` 提炼而来，方法体系一致，按 SKILL.md 开放标准重写。
