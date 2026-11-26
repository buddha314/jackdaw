# Jackdaw development convention

- This is the shared editor source checkout, used across games; do not create a
  separate Jackdaw fork or binary for each game.
- Development `origin`: https://github.com/buddha314/jackdaw.git
- Reference `upstream`: https://github.com/jbuehler23/jackdaw.git
- Develop and publish fixes to the buddha314 fork. Use our fixes without waiting
  for jbuehler23 to accept upstream PRs.
- Preserve these remote roles when fetching, opening PRs, and setting up checkouts.
- Keep upstream integration deliberate; do not replace our development fixes when
  syncing upstream.
- **Fork changes are bug fixes only.** Never adapt the editor to a game: game-specific
  needs belong in the game project, through Jackdaw's own extension points (reflected
  components, `HiddenInGame`, prefabs). Publish fixes only to the buddha314 fork; jbuehler23 is read-only.
- Keep `main` current: merge `upstream/main` regularly, rebuild `-p jackdaw -p jd`
  with the pinned toolchain, and push to `origin`.
- The editor and CLI are system-wide through soft links:
  `~/.cargo/bin/jackdaw` → `target/debug/jackdaw` and `~/.cargo/bin/jd` →
  `target/debug/jd` in this checkout. Do not `cargo install` over them.

## Moving Bevy: avian first

Follow `docs/upgrading-bevy.md` for any Bevy re-pin, including one that arrives
through an upstream merge. In short:

- **Avian sets the limit.** The newest usable Bevy commit is the newest one the
  avian forks build against: jbuehler23's for the Physics module, buddha314's for
  the games. Find it with `scripts/bevy_ceiling.py ceiling --forks
  ../<game>/bevy_main_forks.json` before changing any lockfile. Never pin past it:
  games without physics are not usable games.
- **One Bevy revision everywhere.** The root, `integrations/physics` and
  `integrations/navmesh` lockfiles move together, and games copy the revision from
  here (`tools/jackdaw.sh sync`). Never pin a game to a Bevy this fork has not.
- **Porting Jackdaw to a new Bevy is allowed** alongside bug fixes. Rename only
  Bevy's identifiers, and do it on a `repin/bevy-<rev>` branch in a sibling
  worktree.
- **Forks are allowed when needed** (avian's dependencies such as parry and glamx,
  or Bevy itself), but only under buddha314, wired in with `[patch]`, and kept in
  the game's `bevy_main_forks.json`. Its generator force-pushes those branches.
- Before calling a test failure a regression, check that it passes at the old pin.
  The doc's log keeps the known-failing list and the current ceiling.

## Hard rule: jbuehler23 is read-only

Never push to jbuehler23, whether through a named remote, a direct URL, GitHub CLI,
an API or any other route. Never open pull requests or publish changes to that
account. Fetching and reading are allowed. All pushes and PRs go only to buddha314.
This rule overrides any older instruction to offer fixes upstream. The upstream
remote's push URL is deliberately disabled; do not restore or bypass it.
