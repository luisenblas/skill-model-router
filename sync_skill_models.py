#!/usr/bin/env python3
"""sync_skill_models.py — stamp each skill's `model:` + `effort:` from its power band.

Single source of truth lives in two config files (NOT in the skills):
  - skill_tiers.conf : skill  -> power band     (how much power a skill needs)
  - power_map.conf   : band   -> model[, effort] (which model/effort fills that band today)

For every skill listed in skill_tiers.conf, this writes `power:` (the band, for
human readability), `model:`, and `effort:` (both read by Claude Code — the
skill's effort overrides the session effort while it runs) into that skill's
SKILL.md frontmatter. Idempotent. Skills not listed are never touched.

Usage:
  python3 sync_skill_models.py            # apply
  python3 sync_skill_models.py --check    # dry run, show what would change
  python3 sync_skill_models.py --skills-dir /path/a --skills-dir /path/b

Skill directories (each contains <skill>/SKILL.md), first match wins:
  1. one or more --skills-dir flags
  2. SKILL_DIRS env var, os.pathsep-separated (":" on macOS/Linux)
  3. default: ~/.claude/skills
"""
import argparse, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SKILLS_DIR = "~/.claude/skills"

def resolve_skill_dirs(cli_dirs):
    """CLI flags win, then the SKILL_DIRS env var, then the default."""
    if cli_dirs:
        dirs = cli_dirs
    elif os.environ.get("SKILL_DIRS"):
        dirs = [d for d in os.environ["SKILL_DIRS"].split(os.pathsep) if d]
    else:
        dirs = [DEFAULT_SKILLS_DIR]
    return [os.path.expanduser(d) for d in dirs]

def find_skill(skill_dirs, skill):
    for d in skill_dirs:
        path = os.path.join(d, skill, "SKILL.md")
        if os.path.isfile(path):
            return path
    return None

def load_conf(path):
    """Parse a `key = value` file, ignoring blank lines and # comments."""
    out = {}
    with open(path) as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def set_frontmatter_field(text, key, value):
    """Set `key: value` inside the first --- frontmatter block.
    Replace in place if present, else insert after the `name:` line (or at top).
    Returns (new_text, old_value_or_None)."""
    if not text.startswith("---"):
        raise ValueError("no frontmatter")
    lines = text.split("\n")
    # locate closing fence
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("unterminated frontmatter")

    pat = re.compile(r"^(" + re.escape(key) + r"):\s*(.*)$")
    for i in range(1, end):
        m = pat.match(lines[i])
        if m:
            old = m.group(2).strip()
            lines[i] = f"{key}: {value}"
            return "\n".join(lines), old
    # not found -> insert after name: if present, else right after opening fence
    insert_at = 1
    for i in range(1, end):
        if lines[i].startswith("name:"):
            insert_at = i + 1
            break
    lines.insert(insert_at, f"{key}: {value}")
    return "\n".join(lines), None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", action="append",
                    help="skills directory; repeat for several (or set SKILL_DIRS)")
    ap.add_argument("--tiers", default=os.path.join(HERE, "skill_tiers.conf"))
    ap.add_argument("--map", default=os.path.join(HERE, "power_map.conf"))
    ap.add_argument("--check", action="store_true", help="dry run")
    args = ap.parse_args()

    skill_dirs = resolve_skill_dirs(args.skills_dir)
    tiers = load_conf(args.tiers)
    VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
    # power_map values are "model[, effort]" -> {band: (model, effort_or_None)}
    power_map = {}
    for band, val in load_conf(args.map).items():
        parts = [p.strip() for p in val.split(",")]
        model, effort = parts[0], (parts[1] if len(parts) > 1 else None)
        if effort is not None and effort not in VALID_EFFORTS:
            sys.exit(f"power_map.conf: band '{band}' has invalid effort '{effort}' "
                     f"(valid: {', '.join(sorted(VALID_EFFORTS))})")
        power_map[band] = (model, effort)

    print(f"power map : " + ", ".join(
        f"{b}->{m}" + (f"/{e}" if e else "") for b, (m, e) in power_map.items()))
    print(f"skills    : {len(tiers)} declared in skill_tiers.conf")
    print(f"target    : {os.pathsep.join(skill_dirs)}")
    print(f"mode      : {'CHECK (no writes)' if args.check else 'APPLY'}\n")

    changed = unchanged = errors = 0
    for skill, band in sorted(tiers.items()):
        if band not in power_map:
            print(f"  ! {skill:14s} band '{band}' not in power_map.conf — skipped")
            errors += 1
            continue
        path = find_skill(skill_dirs, skill)
        if path is None:
            print(f"  ! {skill:14s} SKILL.md not found — skipped")
            errors += 1
            continue
        model, effort = power_map[band]
        text = open(path).read()
        try:
            text2, old_model = set_frontmatter_field(text, "model", model)
            text2, _ = set_frontmatter_field(text2, "power", band)
            old_effort = None
            if effort is not None:
                text2, old_effort = set_frontmatter_field(text2, "effort", effort)
        except ValueError as e:
            print(f"  ! {skill:14s} {e} — skipped")
            errors += 1
            continue
        if text2 == text:
            unchanged += 1
            print(f"  = {skill:14s} {band:9s} model={model} effort={effort or '-'} (already)")
        else:
            changed += 1
            arrow = f"{old_model or '<none>'} -> {model}"
            if effort is not None and old_effort != effort:
                arrow += f", effort: {old_effort or '<none>'} -> {effort}"
            print(f"  ~ {skill:14s} {band:9s} model: {arrow}")
            if not args.check:
                open(path, "w").write(text2)

    print(f"\n{changed} changed, {unchanged} unchanged, {errors} errors")
    if errors:
        sys.exit(1)

if __name__ == "__main__":
    main()
