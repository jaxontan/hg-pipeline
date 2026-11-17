"""Director layer: a show bible + an episode shot list -> prompts for every lane.

Nothing here talks to ComfyUI. It only turns structured intent (who, where, shot size, camera
move, action, line) into the text and reference lists the lanes need, so the same shot always
compiles to the same prompt. `pipeline.produce` runs the result.

Files (see workflows/templates/):
  projects/<show>/bible.json          the IP: look, cast, wardrobe, voices, locations
  projects/<show>/episodes/<ep>.json  the shot list for one episode
"""
from __future__ import annotations

import json
import os
import re

# --------------------------------------------------------------------------- camera language
# Codes the shot list may use. Anything not in a table is passed through verbatim, so a
# director can always write a custom phrase instead of a code.
SIZES = {
    "ELS": "extreme wide establishing shot, the figures small in a large environment",
    "LS": "wide shot, full body visible head to toe",
    "MS": "medium shot from the waist up",
    "MCU": "medium close-up from the chest up",
    "CU": "close-up on the face, head filling the upper half of the frame",
    "ECU": "extreme close-up on the eyes",
    "TWO": "two-shot, both people clearly in frame",
    "OTS": "over-the-shoulder shot, the foreground shoulder soft and out of focus",
    "INSERT": "tight insert shot of the object, no faces",
    "POV": "first-person point-of-view shot",
}
ANGLES = {
    "eye": "eye-level camera",
    "low": "low-angle camera looking up, the subject imposing",
    "high": "high-angle camera looking down, the subject diminished",
    "top": "overhead top-down camera",
    "dutch": "dutch-tilted camera, uneasy",
    "profile": "side-profile camera",
    "back": "camera behind the subject, seen from the back",
}
MOVES = {
    "static": "The camera is locked off on a tripod and does not move.",
    "push_in": "The camera drifts in very slowly; the framing tightens only slightly.",
    "pull_out": "The camera drifts back very slowly; the framing widens only slightly.",
    "crash_zoom": "The camera snaps in fast toward the subject in a sudden crash zoom.",
    "pan_left": "The camera pans smoothly to the left.",
    "pan_right": "The camera pans smoothly to the right.",
    "tilt_up": "The camera tilts up from the hands to the face.",
    "tilt_down": "The camera tilts down from the face to the hands.",
    "track_left": "The camera tracks sideways to the left, parallel to the subject.",
    "track_right": "The camera tracks sideways to the right, parallel to the subject.",
    "follow": "The camera follows the subject from behind at walking pace.",
    "lead": "The camera moves backward in front of the subject as they walk toward it.",
    "orbit": "The camera arcs slowly around the subject.",
    "crane_up": "The camera rises smoothly upward.",
    "handheld": "Subtle handheld camera, slight natural shake.",
    "rack_focus": "The focus racks from the foreground to the background.",
}

FPS = 24.0


def _code(table: dict, value: str | None) -> str:
    if not value:
        return ""
    return table.get(value, table.get(str(value).upper(), table.get(str(value).lower(), value)))


def frames_for(seconds: float, fps: float = FPS) -> int:
    """LTX wants 8k+1 frames."""
    return max(1, round(seconds * fps / 8)) * 8 + 1


# --------------------------------------------------------------------------- show / episode
class Show:
    def __init__(self, root: str, name: str):
        self.root, self.name = root, name
        self.dir = os.path.join(root, "projects", name)
        path = os.path.join(self.dir, "bible.json")
        if not os.path.exists(path):
            raise SystemExit(f"no bible at {path} - copy workflows/templates/bible.json there")
        with open(path, encoding="utf-8") as fh:
            self.bible = json.load(fh)
        self.style = self.bible.get("style", {})
        self.chars = self.bible.get("characters", {})
        self.locs = self.bible.get("locations", {})
        self.seed = int(self.bible.get("seed", 20261116))

    # ---- lookups ---------------------------------------------------------
    def char(self, cid: str) -> dict:
        if cid not in self.chars:
            raise SystemExit(f"character {cid!r} is not in the bible ({', '.join(self.chars)})")
        return self.chars[cid]

    def loc(self, lid: str) -> dict:
        if lid not in self.locs:
            raise SystemExit(f"location {lid!r} is not in the bible ({', '.join(self.locs)})")
        return self.locs[lid]

    def wardrobes(self, cid: str) -> dict:
        w = self.char(cid).get("wardrobe") or {"default": ""}
        return {"default": w} if isinstance(w, str) else w

    def wardrobe_key(self, cid: str, shot: dict | None = None) -> str:
        chosen = ((shot or {}).get("wardrobe") or {}).get(cid)
        keys = list(self.wardrobes(cid))
        if chosen and chosen not in keys:
            raise SystemExit(f"{cid} has no wardrobe {chosen!r} ({', '.join(keys)})")
        return chosen or keys[0]

    # ---- asset names (relative to ComfyUI's input dir) --------------------
    def asset(self, name: str) -> str:
        return f"{self.name}/{name}.png"

    def char_sheet(self, cid: str, wardrobe: str) -> str:
        return self.asset(f"char_{cid}_{wardrobe}")

    def loc_plate(self, lid: str) -> str:
        return self.asset(f"loc_{lid}")

    def episode(self, ep: str) -> dict:
        path = os.path.join(self.dir, "episodes", f"{ep}.json")
        if not os.path.exists(path):
            raise SystemExit(f"no episode at {path}")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        seen = set()
        for shot in data["shots"]:
            sid = shot.get("id")
            if not sid or sid in seen:
                raise SystemExit(f"{ep}: every shot needs a unique id (problem at {sid!r})")
            seen.add(sid)
            for cid in shot.get("characters", []):
                self.char(cid)
                self.wardrobe_key(cid, shot)
            if shot.get("location"):
                self.loc(shot["location"])
            d = shot.get("dialogue")
            if d:
                self.char(d["who"])
        return data

    # ---- asset prompts ----------------------------------------------------
    def face_prompt(self, cid: str, wardrobe: str) -> str:
        c = self.char(cid)
        return (f"Photoreal studio casting portrait, head and shoulders, facing the camera. "
                f"{c['appearance']}. Wearing {self.wardrobes(cid)[wardrobe]}. Neutral relaxed "
                f"expression, plain light-grey seamless backdrop, soft even light, 85mm lens, "
                f"natural skin texture, sharp focus.")

    def face_variant_prompt(self, cid: str, wardrobe: str) -> str:
        return (f"Photoreal studio casting portrait, head and shoulders, facing the camera. The "
                f"same person as image 1, identical face, identical hair, now wearing "
                f"{self.wardrobes(cid)[wardrobe]}. Neutral relaxed expression, plain light-grey "
                f"seamless backdrop, soft even light, 85mm lens, sharp focus.")

    def body_prompt(self, cid: str, wardrobe: str) -> str:
        return (f"Photoreal studio casting photo, full-length front view, head to toe. The same "
                f"person as image 1, identical face, identical hair, wearing "
                f"{self.wardrobes(cid)[wardrobe]}. Standing straight, arms relaxed at the sides, "
                f"plain light-grey seamless backdrop, soft even light, sharp focus.")

    def plate_prompt(self, lid: str) -> str:
        look = self.style.get("look", "")
        return f"{self.loc(lid)['prompt']} Empty of people. {look} Vertical composition."

    # ---- shot prompts -----------------------------------------------------
    def _refs(self, shot: dict) -> tuple[list[str], dict[str, int], int | None]:
        refs, index = [], {}
        for cid in shot.get("characters", []):
            refs.append(self.char_sheet(cid, self.wardrobe_key(cid, shot)))
            index[cid] = len(refs)
        loc_idx = None
        if shot.get("location"):
            refs.append(self.loc_plate(shot["location"]))
            loc_idx = len(refs)
        return refs, index, loc_idx

    def keyframe(self, shot: dict) -> tuple[str, list[str]]:
        """Prompt + reference list for the still that opens the shot."""
        refs, index, loc_idx = self._refs(shot)
        subst = {cid: f"the {self.char(cid).get('noun', 'person')} from image {n}"
                 for cid, n in index.items()}
        action = _fill(shot.get("action", ""), subst)
        parts = [self.style.get("look", "Photoreal cinematic film still.").rstrip(".") + ".",
                 "Vertical 9:16 frame, " + ", ".join(x for x in (
                     _code(SIZES, shot.get("size")), _code(ANGLES, shot.get("angle")),
                     shot.get("lens")) if x) + "."]
        for cid, n in index.items():
            c = self.char(cid)
            parts.append(f"Image {n} is the casting sheet (face and full body) of the "
                         f"{c.get('noun', 'person')}: keep exactly the same face, age, hair and "
                         f"clothes ({self.wardrobes(cid)[self.wardrobe_key(cid, shot)]}).")
        if loc_idx:
            parts.append(f"The setting is the place in image {loc_idx}: "
                         f"{self.loc(shot['location']).get('short', 'same architecture and light')}.")
        elif shot.get("setting"):
            parts.append(shot["setting"].rstrip(".") + ".")
        if index and not any(s in action for s in subst.values()):
            action = f"{' and '.join(subst.values())} {action}"
        if action:
            parts.append(action[0].upper() + action[1:].rstrip(".") + ".")
        if shot.get("light"):
            parts.append(shot["light"].rstrip(".") + ".")
        parts.append("One single continuous photograph filling the whole frame, shot on location.")
        return " ".join(parts), refs

    def video(self, shot: dict) -> str:
        """Prompt for the motion pass. The keyframe already fixes who and where."""
        subst = {cid: self.char(cid).get("token", f"the {self.char(cid).get('noun', 'person')}")
                 for cid in shot.get("characters", [])}
        parts = []
        motion = _fill(shot.get("motion") or shot.get("action", ""), subst)
        if motion:
            parts.append(motion[0].upper() + motion[1:].rstrip(".") + ".")
        d = shot.get("dialogue")
        if d and not d.get("vo"):
            who = subst.get(d["who"]) or self.char(d["who"]).get("token", "the person")
            mood = f", {d['acting']}" if d.get("acting") else ""
            # The wav carries the language; the prompt only has to say that this person talks.
            parts.append(f"{who[0].upper() + who[1:]} is talking, the lips moving naturally "
                         f"in sync with the voice{mood}. Nobody else speaks.")
        elif not d:
            parts.append("Nobody speaks.")
        parts.append(_code(MOVES, shot.get("move") or "static"))
        size = _code(SIZES, shot.get("size"))
        if size:
            parts.append(size[0].upper() + size[1:] + ".")
        parts.append(self.style.get("video", "Photoreal, cinematic, shallow depth of field, "
                                             "natural motion, consistent face."))
        if shot.get("sound") and not (d and not d.get("vo")):
            parts.append("Sound: " + shot["sound"].rstrip(".") + ".")
        return " ".join(parts)

    def voice(self, shot: dict) -> tuple[str, str] | None:
        d = shot.get("dialogue")
        if not d:
            return None
        base = self.char(d["who"]).get("voice", "")
        emo = d.get("emotion")
        return d["text"], (f"{base}，{emo}" if emo else base)


def _fill(text: str, subst: dict[str, str]) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: subst.get(m.group(1), m.group(0)), text)
