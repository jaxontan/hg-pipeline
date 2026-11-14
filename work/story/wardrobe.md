# Canonical wardrobe — prompt clauses

Every keyframe and clip prompt must carry the clause for whichever character is legible in frame.
Without this, the same character comes back in different clothes from shot to shot: 苏念 has
appeared as a black sleeveless top (s004), a white blouse (s003) and a dark jacket (s008) in the
same episode. That is not a model failure, it is a missing spec — the model invents whatever the
prompt leaves open.

Source: `premise_laotang.md` §Cast. Do not invent outfits; if a scene needs a change of clothes
(the chef's coat), it is a beat, and it gets its own clause.

## Clauses (append to the prompt, in this exact wording)

| Character | Clause |
|---|---|
| **苏念** L1 | `Chinese woman of 26, hair tied back with one loose strand, wearing a plain dark apron over a worn oatmeal knit sweater, sleeves pushed up to the forearm, cuffs bunched` |
| **顾衍** L2 | `Chinese man of 30, dark shirt with no tie, sleeves rolled to the forearm, a single wristwatch` |
| **苏建国** L3 | `Chinese man of 52, shiny short-sleeve shirt, a gold chain at the neck, a jade ring` |
| **小满** L4 | `Chinese girl of 12, school uniform, oversized backpack, hair clip` |
| **老周** minor | `Chinese man in his sixties, retired cook, plain white undershirt and apron` |

Late-episode variant for 苏念, once she takes over the kitchen:

`Chinese woman of 26, hair tied back with one loose strand, wearing a clean white chef's coat`

## Negative clause (append to the negative prompt)

`bare shoulders, sleeveless top, tank top, crop top, modern fashion, mismatched outfit, changing clothes between shots`

## Why sleeves matter beyond wardrobe

Long sleeves also cover the arm-to-torso junction of the white model, which is where the depth pass
has a thin seam. Two of the three keyframe defects (the armpit wedges on s004) disappear when the
character is clothed as specified.

## Correction, 13 Nov — `sleeves down` was a clause the model never obeyed

The clause said `sleeves down`. Every frame generated against it came back with the cuffs bunched at
the forearm: `s003b` (00017), `s004d` (00016) and `s004g` (00019) all agree, in three separate
generations, from two rigs. The wording lost every time, and it lost consistently, so the spec was
wrong rather than the samples. It now says what the film actually shows. A clause the model overrides
is worse than no clause: it teaches you to trust the text instead of checking the frame.

The apron is **not** removed. `s004g` reads as her steadying the apron at the waist, not pulling it
off, and that is the better outcome: she is still wearing it through the alley and the street stall,
which is where the next four units place her.
