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

## Hard rule: jbuehler23 is read-only

Never push to jbuehler23, whether through a named remote, a direct URL, GitHub CLI,
an API or any other route. Never open pull requests or publish changes to that
account. Fetching and reading are allowed. All pushes and PRs go only to buddha314.
This rule overrides any older instruction to offer fixes upstream. The upstream
remote's push URL is deliberately disabled; do not restore or bypass it.
