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
