# Clone notes — my-hongguo-topic-expert

**Date:** 2026-11-14
**Source:** `hongguo-short-drama-topic-expert` (marketplace `experts`, 红果短剧选题专家 / Short Drama Topic Master, agent type, `06-ContentCreative`)
**Clone:** `my-hongguo-topic-expert` at `C:\Users\admin\.workbuddy\plugins\marketplaces\my-experts\plugins\my-hongguo-topic-expert`

## Fidelity

Verified by SHA-256 comparison of every file: **496 / 496 files are byte-identical to the source**, with the sole exception of the mandatory identity substitution `hongguo-short-drama-topic-expert` → `my-hongguo-topic-expert` (applied at byte level, so LF line endings are preserved exactly).

Differences that are *identity only* (cannot be avoided — a clone that reuses the original ID would collide with it):

| Item | Source | Clone |
|---|---|---|
| `plugin.json` `name` / `plugin` / `agentName` | `hongguo-short-drama-topic-expert` | `my-hongguo-topic-expert` |
| `plugin.json` `agents` / `skills` paths | `hongguo-short-drama-topic-expert…` | `my-hongguo-topic-expert…` |
| Agent MD filename | `agents/hongguo-short-drama-topic-expert.md` | `agents/my-hongguo-topic-expert.md` |
| Knowledge-base folder | `skills/hongguo-short-drama-topic-expert-knowledge-base/` | `skills/my-hongguo-topic-expert-knowledge-base/` |
| Agent MD frontmatter `name`, `skills`; KB `SKILL.md` `name` + agent-path reference | old ID | new ID |

All display fields (`displayName`, `profession`, `displayDescription`, `tags`, `quickPrompts`, `defaultInitPrompt`, `categoryId`, `author`, `version`) are unchanged, so the clone presents identically to the original in the Expert Center.

Not copied (not package content): source `.downloaded_at` (marketplace install timestamp).
Platform artifact in the clone: `.created-by-session` (written by `register_expert.py`, consumed by the app on detection).

## Avatar caveat

The user chose a **newly generated** avatar, but the image-generation call was declined at the permission prompt and was not retried. Therefore `avatars/expert.png` is a **byte-for-byte copy of the original avatar** (512×512 PNG, 379,887 bytes) — the clone currently looks identical to the marketplace original.

To make it visually distinct, either:
1. Ask again for image generation (≈5–10 credits), or
2. Drop your own PNG/JPG at `avatars/expert.png` (512×512, ≤500 KB), then re-run `validate_expert.py` + `register_expert.py`.

## Provenance / rights

The source package is a marketplace expert authored by 阿杰. This clone is a local private copy for the user's own editing; redistribution or resale of the cloned package may require the original author's authorisation.
