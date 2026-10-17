# skill-model-router

Regulate Claude Code skills by **power band**, not by model name, so nothing
breaks when models are renamed, retired, or replaced.

## The idea
Skills should declare *how much power they need*, not *which model*. Specific ids
(`claude-fable-5`, `claude-opus-4-8`) rot every time the model lineup changes. Two
config files hold all the policy; a script stamps it into each skill's frontmatter.

- **`skill_tiers.conf`**, `skill = band`. How much power each skill needs.
- **`power_map.conf`**, `band = model[, effort]`. Which model + effort level
  fills each band *today*. Effort (low/medium/high/xhigh/max) is stamped into
  each skill's `effort:` frontmatter and overrides the session effort while the
  skill runs; omit it to leave effort untouched.

Bands: `flagship` (quality is the point), `content` (high-quality but
cost-capped), `synthesis` (briefings/note-writing, medium effort), `routine`
(filing/syncs, low effort), `fast`.

Model values are best as **tier aliases** (`opus`/`sonnet`/`haiku`/`fable`) ,
they auto-track the latest model in that tier, so a new release needs zero edits.
Use a specific id only for a tier with no alias.

## Run
```
python3 sync_skill_models.py --check   # preview
python3 sync_skill_models.py           # apply -> writes power: + model: + effort: into each SKILL.md
```
Skill directories (each holds `<skill>/SKILL.md`), first match per skill wins:

```
python3 sync_skill_models.py --skills-dir ~/.claude/skills --skills-dir ./.claude/skills
SKILL_DIRS="$HOME/.claude/skills:$HOME/work/skills" python3 sync_skill_models.py
```
Order of precedence: `--skills-dir` flags, then the `SKILL_DIRS` env var (separated by `:`), then the default `~/.claude/skills`.
The skill names in `skill_tiers.conf` are examples. Replace them with your own.

Requires Python 3.8+ and no other dependencies. Licensed under MIT.
Idempotent. Skills not in `skill_tiers.conf` are never touched (they inherit the session model).

## The only manual decision left
"A new, more powerful but pricier model appeared, do I want to pay for it?" is a
cost/quality judgment no system can make for you. Here it costs **one line**:

- **Fable on flagship:** set `flagship = fable, high` in `power_map.conf`, run
  the script. All flagship skills flip.
- **Fable off flagship:** set `flagship = opus, high`, rerun. Never a dead pin.

Everything else, new Opus/Sonnet/Haiku versions, renames, retirements, is
absorbed automatically by the aliases with no action at all.
