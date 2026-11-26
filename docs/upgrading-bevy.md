# Upgrading Bevy and Jackdaw: avian first

Jackdaw builds on Bevy's git `main`, and so does every game built with it. The
games need physics, and avian has no release for Bevy main: it and its helpers
come from forks. **The newest Bevy commit we can use is decided by those forks,
not by Bevy or by Jackdaw.** So every upgrade starts with avian, finds how far
it can go (the *ceiling*), and only then moves Jackdaw and the games to it.

## The chain and who owns what

One Bevy revision is shared by everything; it is the one in **this fork's root
`Cargo.lock`**. Games copy it from there (`tools/jackdaw.sh sync` in each game).

```
Bevy main ──▶ avian forks (ceiling) ──▶ buddha314/jackdaw main ──▶ games
                                        (root, physics, navmesh      (compatibility.json,
                                         lockfiles: one Bevy rev)     Cargo.lock)
```

| What | Where | Used by | We can push? |
| --- | --- | --- | --- |
| Jackdaw | `buddha314/jackdaw` main | everything | yes |
| Jackdaw upstream | `jbuehler23/jackdaw` main | merged into ours | **never** (read-only, AGENTS.md) |
| avian2d/avian3d for the Physics module | `jbuehler23/avian` `bevy-main` (with its own `bevy_heavy`, `bevy_transform_interpolation`, `glam_matrix_extras` forks) | `integrations/physics` | **never** |
| avian3d + helpers + `bevy_mod_outline` for games | `buddha314/{avian,bevy_heavy,bevy_transform_interpolation,glam_matrix_extras,bevy_mod_outline}` `bevy-main` | games, via `[patch.crates-io]` | yes |
| Their generator | `stubby-music/tools/bevy_main_forks.py` + `bevy_main_forks.json` | regenerates the buddha314 branches from each release | — |

**We may fork more when needed** (user direction, 2026-11-25): avian's own
dependencies (`parry`, `glamx`, ...) and Bevy itself, always under buddha314. See
step 3 for how, and for why a fork is the last resort rather than the first.

## Step 1: find the ceiling

```bash
scripts/bevy_ceiling.py walls                     # what changed in Bevy since our pin
scripts/bevy_ceiling.py ceiling \
    --forks ../stubby-music/bevy_main_forks.json  # one --forks per game
scripts/bevy_ceiling.py probe <rev> --forks ...   # check one commit
```

`ceiling` builds small probe crates, one per fork set, at Bevy revisions between
our pin and Bevy main's tip, and bisects for the newest one where they all
compile. The `physics` probe takes avian exactly as `integrations/physics`
declares it; each `--forks` probe resolves the same graph the game does. A probe
also fails if its graph ends up with two copies of Bevy. Bisecting assumes a
break stays broken, which holds for dependency bumps (the usual cause). Read the
`walls` list alongside it: breaks cluster at the `!` lines, which are glam,
wgpu and similar bumps, plus MSRV raises.

Probes use the checkout's `rust-toolchain.toml`. A commit that raises Bevy's
`rust-version` past it is reported as such, and probed with the newer toolchain
if rustup has it (`rustup toolchain install <ver> --profile minimal -c clippy`).

## Step 2: choose the target

The target is the **ceiling**, unless:

- **Upstream Jackdaw is already past the ceiling.** We cannot merge upstream
  without leaving the forks behind. Either raise the ceiling (step 3) or hold the
  upstream merge until we can. Check with
  `scripts/bevy_ceiling.py probe <upstream's bevy rev> --forks ...`.
- **The ceiling needs a newer rustc.** That is a toolchain bump too: Jackdaw's
  `rust-toolchain.toml` (the games' `jackdaw.sh sync` copies it into
  `compatibility.json` and their own toolchain file).
- **Jackdaw's port at the ceiling is large** (step 4 shows this). Taking an
  earlier commit is fine. Any commit at or below the ceiling is a valid pin, and
  moving by stages is cheaper than one huge port.

## Step 3 (only if needed): raise the ceiling with a fork

Do this only when the target must be past the ceiling. Otherwise wait for
upstream avian or parry, which usually catch up within days of a Bevy bump.

1. **Find the blocking crate.** In the failing probe dir
   (`~/.cache/bevy-ceiling/probes/<name>`) run
   `cargo tree -i <dep>@<old version>`, e.g. `cargo tree -i glam@0.33.12`. Port
   from the leaves up. For a glam bump that is `glamx` → `parry2d/3d` →
   `glam_matrix_extras` → `bevy_heavy`, `bevy_transform_interpolation` →
   `avian`.
2. **Fork under buddha314 only** (`gh repo fork <upstream> --clone=false`), on a
   `bevy-main` branch. Changes are mechanical: version bumps and API renames. If a
   fix needs a design decision, it belongs upstream: wait for it.
3. **Wire it in with `[patch]`, not by editing dependency lines.** Games already
   use `[patch.crates-io]`. For Jackdaw's Physics module, add
   `[patch."https://github.com/jbuehler23/avian"]` (or `[patch.crates-io]` for
   `parry3d`) to `integrations/physics/Cargo.toml`. That leaves upstream's own
   lines untouched, so upstream merges stay clean.
4. **Make `bevy_main_forks.py` keep it.** That script rebuilds each branch from
   the release in `bevy_main_forks.json` (`base`) and **force-pushes**, so a
   hand-made commit on `bevy-main` disappears on the next game sync. Put the port
   on its own branch, point the fork's `base` at it, and add any newly forked
   crate (e.g. `parry3d`) to the JSON so its patch is generated too.
5. Re-run step 1. The ceiling should now be past the old blocker.

**Forking Bevy itself** is for a fix we cannot wait on, not for chasing main.
Every Bevy declaration in every workspace must resolve to the same source, or
Cargo builds two Bevys and nothing links. So never edit the `bevy = { git = ... }`
lines (there are dozens). Instead add
`[patch."https://github.com/bevyengine/bevy"]` pointing at the buddha314 fork to
**every** top-level workspace: Jackdaw root, `integrations/physics`,
`integrations/navmesh`, each game, and each avian fork you build alone. Then
record it here.

## Step 4: port Jackdaw to the target

Work on a branch, `repin/bevy-<short rev>`, in a sibling worktree
(`git worktree add ../jackdaw-repin -b repin/bevy-<rev> main`). The shared
checkout stays clean and on `main`, which the games' sync requires.

1. **Move all three lockfiles to the same revision.** `cargo xtask fast` fails if
   they differ (`git_deps` check).
   ```bash
   REV=<full sha>
   cargo update -p bevy --precise $REV
   (cd integrations/physics && cargo update -p bevy --precise $REV)
   (cd integrations/navmesh && cargo update -p bevy --precise $REV)
   ```
   If a fork moved in step 3, also run
   `cargo update -p avian3d -p avian2d -p bevy_heavy -p bevy_transform_interpolation -p glam_matrix_extras`
   in `integrations/physics`.
2. **See every error at once.** Run this in each of the three workspaces:
   `cargo check --workspace --all-targets --keep-going --message-format short`.
   A crate low in the graph (e.g. `jackdaw_runtime`) hides everything above
   it, so fix it first and re-run.
3. **Read Bevy's migration guides** instead of guessing:
   ```bash
   B=~/.cache/bevy-ceiling/bevy.git
   git -C $B diff --name-only --diff-filter=A <old rev> $REV -- _release-content/migration-guides
   git -C $B show $REV:_release-content/migration-guides/<file>.md
   ```
4. **Rename only Bevy's names.** When Bevy renames a type, change uses of
   *Bevy's* type. Jackdaw's own similarly named types keep their names
   (e.g. `AnimationGraphDef` stayed when Bevy's `AnimationGraph` became
   `BlendGraph`). Upstream is likely to make the same edit later, and identical
   one-line edits merge cleanly where gratuitous renames conflict.

## Step 5: verify, proportionate to the change

We are prototyping (stubby-music's version policy), so test enough to be sure
and no more:

- **Always:** `cargo xtask fast`, which runs fmt, the dependency checks, clippy
  with `-D warnings`, and lib tests. Also `cargo nextest run --workspace` in
  `integrations/physics` and `integrations/navmesh`. Needs
  `cargo install cargo-nextest --locked`.
- **When the port touched editor or runtime behaviour** (not just names): run the
  integration themes that cover it, e.g.
  `cargo nextest run --test editor -E 'test(/^inspector::/)'`. Run all of
  `cargo xtask integration` only for a large port.
- **A failure is a regression only if it passes at the old pin.** Run the failing
  tests in a worktree at the old pin before fixing anything. The known-failing
  list below saves that step.
- **Then the games:** after the PR merges, run `tools/jackdaw.sh sync` in each
  game (it moves Bevy, the forks and the toolchain from this lockfile), build the
  game, and do one bounded 20-second Play via `tools/jackdaw_timed_test.py`.

## Step 6: record it

Append an entry to the log below: date, old → new pin, the ceiling and what
blocks past it, ports done, known failures, rollback. Update the game's version
policy log when its pin moves.

## Merging upstream Jackdaw afterwards

Our pin may now be ahead of, or behind, upstream's.

- **`Cargo.lock` conflict:** keep either side, then re-run step 4.1 with the
  newer of the two revisions, as long as it is at or below the ceiling (`probe`
  it). If upstream's revision is past the ceiling, stop: that is step 2's first
  case.
- **Code conflicts from the same Bevy migration:** take upstream's side. It is
  the same change and keeps our diff from upstream small.

## Log

### 2026-11-25: Bevy `c9c397ba` → `526f9e40` (the ceiling)

- Moved from Bevy main `c9c397ba` (2026-10-21) in all three lockfiles; rust stays 1.99.0.
  Landed together with this document and `scripts/bevy_ceiling.py`.
- **Ceiling `526f9e40`** (2026-11-07, "Allow AssetReaders to not be tied to their
  path lifetime"), 90 commits past the pin. Both fork sets (jbuehler23's and the
  game's buddha314 set) build there with no changes.
- **Blocked past it by glam 0.34** (`098a4bfb1`, 2026-11-08). `parry2d/3d 0.31.1`
  → `glamx 0.3.1` require `glam ^0.33`, and no release supports 0.34 yet.
  `glam_matrix_extras` (both forks) is on 0.33 too. Raising the ceiling means
  forking glamx and parry (step 3).
- Next walls: rustc **1.100** from `41a1282e3` (2026-11-13); taffy 0.16 at the
  tip `71df1738`.
- Port to `526f9e40` (26 files):
  - `AnimationGraph*` → `BlendGraph*`, `AnimationNodeIndex` → `BlendNodeIndex`,
    `Animatable*` → `Blendable*` (Bevy's names only; #26367).
  - `AssetReader::read`/`read_meta` take `CowArc<'a, Path>`: the readers in
    `jackdaw_runtime/src/{twin,texture_import}.rs` and their callers (#26092).
  - `{Align,Justify}{Items,Content}::Default` → `::Normal` (#26344). The
    inspector's "Default" labels are unchanged.
  - `FocusPolicy` removed (#26094): dropped in `lod_bar.rs`, which already had
    `Pickable::IGNORE`.
- Verified: `xtask fast` 3,602/3,602; physics 49/49; navmesh 69/69;
  `xtask integration` 7,396/7,401.
- **Known-failing at both `c9c397ba` and `526f9e40`** (identical messages, not
  caused by the re-pin):
  - `controls::popovers::a_popover_is_placed_by_the_widget_against_its_anchor`
    (placed `Right`, expected `Left`)
  - `operators::tileset_bits::the_brush_paints_in_its_own_set_whatever_header_was_clicked`
  - `operators::tileset_dock::an_auto_import_keeps_its_setup_when_it_opens_the_tileset`
  - `operators::tileset_dock::one_set_lists_its_terrains_alone_and_a_second_brings_headers`
    (these three: feathers `ColorSwatchValue` inserted on a despawned entity)
  - `operators::tileset_browser::the_packed_copy_and_its_tileset_are_pictured_as_a_plain_sheet`
- Games still pin `c9c397ba` until each runs `tools/jackdaw.sh sync`.
- Rollback: revert this PR's merge commit (lockfiles and port together).
