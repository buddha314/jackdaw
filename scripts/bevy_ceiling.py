#!/usr/bin/env python3
"""Find the newest Bevy main commit our physics forks build against.

Jackdaw follows Bevy's git main, but avian and its helpers have no Bevy-main
release: they come from `bevy-main` branches of forks. Those forks break whenever
Bevy moves a dependency they share (glam, wgpu, the MSRV). This script finds the
"avian ceiling": the newest Bevy main commit at which every probe still compiles.
See docs/upgrading-bevy.md for the process it is step 1 of.

    scripts/bevy_ceiling.py walls   [--from REV] [--to REV]
    scripts/bevy_ceiling.py probe   REV [--forks FILE ...]
    scripts/bevy_ceiling.py ceiling [--from REV] [--to REV] [--forks FILE ...]

walls    Bevy commits in (from, to] that change a third-party version requirement
         or rust-version. Breaks cluster here; read this list before bisecting.
probe    Build every probe at REV and report pass/fail per probe.
ceiling  Bisect (from, to] on Bevy's first-parent history for the newest commit
         where every probe passes. Assumes a break stays broken, which holds for
         dependency bumps; confirm the answer with `probe`.

--from defaults to the Bevy commit in this checkout's Cargo.lock, --to to Bevy
main's tip. Probes:

  physics      avian2d/avian3d exactly as integrations/physics declares them
               (always run).
  forks:<name> one per --forks FILE, a game's bevy_main_forks.json: every listed
               crate, with its [patch.crates-io] pointing at the fork branch, the
               same graph the game resolves (e.g. ../stubby-music/bevy_main_forks.json).

Probes are tiny crates under ~/.cache/bevy-ceiling, sharing one target dir. They
use this checkout's rust-toolchain; a commit that needs a newer rustc is reported
as such (and probed with that toolchain if rustup has it). Nothing here edits the
checkout or pushes anywhere.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get('BEVY_CEILING_CACHE', Path.home() / '.cache/bevy-ceiling'))
BEVY_URL = 'https://github.com/bevyengine/bevy'
BEVY_GIT = CACHE / 'bevy.git'
TARGET = CACHE / 'target'
# Features beyond the defaults that the games turn on; a probe must compile the
# code paths a game compiles, or it can pass where the game fails.
EXTRA_FEATURES = {
    'avian3d': ['3d', 'parry-f32', 'parallel', 'collider-from-mesh', 'debug-plugin'],
    'avian2d': ['2d', 'parry-f32', 'parallel', 'debug-plugin'],
}
# Third-party crates whose version moves are the usual walls. Anything else that
# changes a version requirement is listed too; these are just flagged.
KNOWN_WALLS = ('glam', 'wgpu', 'naga', 'winit', 'taffy', 'parry', 'accesskit')


def run(*args, cwd=None, capture=False, check=True, env=None):
    result = subprocess.run(args, cwd=cwd, text=True, check=check, env=env,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None)
    return result.stdout.strip() if capture else result.returncode


def bevy(*args, check=True):
    return run('git', '-C', str(BEVY_GIT), *args, capture=True, check=check)


def fetch_bevy():
    if not BEVY_GIT.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        run('git', 'clone', '-q', '--bare', '--filter=blob:none', BEVY_URL, str(BEVY_GIT))
    run('git', '-C', str(BEVY_GIT), 'fetch', '-q', 'origin', '+refs/heads/main:refs/heads/main')


def locked_bevy(lock_path=ROOT / 'Cargo.lock'):
    lock = tomllib.loads(lock_path.read_text())
    source = next(p['source'] for p in lock['package'] if p['name'] == 'bevy')
    return source.rsplit('#', 1)[1]


def toolchain():
    return tomllib.loads((ROOT / 'rust-toolchain.toml').read_text())['toolchain']['channel']


def version_key(v):
    return tuple(int(x) for x in re.findall(r'\d+', v)[:3])


def required_rust(rev):
    text = bevy('show', f'{rev}:Cargo.toml')
    match = re.search(r'(?m)^rust-version\s*=\s*"([^"]+)"', text)
    return match[1] if match else None


def first_parent(frm, to):
    out = bevy('rev-list', '--first-parent', '--reverse', f'{frm}..{to}')
    return out.splitlines()


def describe(rev):
    return bevy('log', '-1', '--format=%h %ad %s', '--date=short', rev)


# ---------------------------------------------------------------- walls

# Manifest keys that look like `key = "value"` but are not dependencies (Bevy's
# [[example]] tables and package metadata).
METADATA_KEYS = {'version', 'name', 'path', 'description', 'category', 'edition', 'license',
                 'repository', 'documentation', 'homepage', 'readme', 'resolver', 'wasm',
                 'doc-scrape-examples', 'hidden', 'required-features', 'crate-type'}
DEP_LINE = re.compile(r'^[+-]\s*([A-Za-z0-9_-]+)\s*=\s*(?:\{[^}]*version\s*=\s*)?"([^"]+)"')


def walls(frm, to):
    found = []
    for rev in first_parent(frm, to):
        diff = bevy('show', '--format=', '-U0', rev, '--', '*Cargo.toml', 'Cargo.toml')
        changes = {}
        for line in diff.splitlines():
            if line.startswith(('+++', '---')):
                continue
            if m := re.match(r'^[+-]\s*rust-version\s*=\s*"([^"]+)"', line):
                changes.setdefault('rust-version', set()).add(m[1])
                continue
            m = DEP_LINE.match(line)
            if not m or m[1].startswith('bevy') or m[1] in METADATA_KEYS:
                continue
            changes.setdefault(m[1], set()).add(m[2])
        # A version requirement that only moved between members is not a bump.
        bumps = {name: sorted(v, key=version_key) for name, v in changes.items() if len(v) > 1}
        if bumps:
            found.append((rev, bumps))
    return found


def print_walls(frm, to):
    found = walls(frm, to)
    print(f'{len(first_parent(frm, to))} first-parent commits in {frm[:9]}..{to[:9]}; '
          f'{len(found)} change a third-party requirement or rust-version:')
    for rev, bumps in found:
        flag = '!' if any(n == 'rust-version' or n.startswith(KNOWN_WALLS) for n in bumps) else ' '
        text = ', '.join(f'{n} {" -> ".join(v)}' for n, v in bumps.items())
        print(f' {flag} {describe(rev)}\n      {text}')
    print("'!' marks the usual breakers (glam, wgpu, MSRV, ...). Try the parent of the first one.")


# ---------------------------------------------------------------- probes

def physics_probe():
    manifest = tomllib.loads((ROOT / 'integrations/physics/Cargo.toml').read_text())
    deps = {name: spec for name, spec in manifest['workspace']['dependencies'].items()
            if name.startswith('avian')}
    return 'physics', deps, {}


def forks_probe(path):
    config = json.loads(Path(path).read_text())
    deps, patch = {}, {}
    for fork in config['forks']:
        major_minor = '.'.join(fork['version'].split('.')[:2])
        spec = {'version': f'^{major_minor}'}
        if fork['crate'] in EXTRA_FEATURES:
            spec.update({'default-features': False, 'features': EXTRA_FEATURES[fork['crate']]})
        deps[fork['crate']] = spec
        patch[fork['crate']] = {'git': fork['fork'], 'branch': config['branch']}
    name = Path(path).resolve().parent.name
    return f'forks:{name}', deps, patch


def toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return '[' + ', '.join(toml_value(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{ ' + ', '.join(f'{k} = {toml_value(v)}' for k, v in value.items()) + ' }'
    raise TypeError(value)


def write_probe(name, deps, patch, rust):
    path = CACHE / 'probes' / re.sub(r'[^A-Za-z0-9_-]', '-', name)
    if path.exists():
        shutil.rmtree(path)
    (path / 'src').mkdir(parents=True)
    (path / 'src/lib.rs').write_text('')
    lines = ['[package]', 'name = "bevy_ceiling_probe"', 'version = "0.0.0"', 'edition = "2024"',
             'publish = false', '', '[dependencies]',
             f'bevy = {{ git = "{BEVY_URL}", branch = "main", default-features = false }}']
    lines += [f'{n} = {toml_value(s)}' for n, s in deps.items()]
    if patch:
        lines += ['', '[patch.crates-io]'] + [f'{n} = {toml_value(s)}' for n, s in patch.items()]
    (path / 'Cargo.toml').write_text('\n'.join(lines) + '\n')
    (path / 'rust-toolchain.toml').write_text(f'[toolchain]\nchannel = "{rust}"\n')
    return path


def installed(rust):
    out = run('rustup', 'toolchain', 'list', capture=True, check=False)
    return any(line.startswith(rust) for line in out.splitlines())


def summarize(output):
    """Which crate failed and its first error, without paths: one short line."""
    lines = output.splitlines()
    crates = [m[1] for l in lines if (m := re.search(r'could not compile `([^`]+)`', l))]
    first = next((re.sub(r'^.*?(error(\[E\d+\])?:)', r'\1', l) for l in lines
                  if re.search(r'error(\[E\d+\])?:', l) and 'could not compile' not in l), '')
    if crates:
        return f'`{crates[0]}` does not compile: {first[:160]}'
    return first[:200] or output.strip()[-200:]


def probe(rev, probes, quiet=False):
    """Map probe name -> (ok, detail). Every probe builds against exactly `rev`."""
    rev = bevy('rev-parse', rev)
    rust = toolchain()
    need = required_rust(rev)
    if need and version_key(need) > version_key(rust):
        if not installed(need):
            return {name: (False, f'needs rustc {need} (pinned {rust}; not installed)')
                    for name, _, _ in probes}
        rust = need
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET))
    results = {}
    for name, deps, patch in probes:
        path = write_probe(name, deps, patch, rust)
        steps = [('cargo', 'generate-lockfile', '-q'),
                 ('cargo', 'update', '-q', '-p', 'bevy', '--precise', rev),
                 ('cargo', 'check', '-q', '--message-format', 'short')]
        detail = ''
        for step in steps:
            out = subprocess.run(step, cwd=path, env=env, text=True, capture_output=True)
            if out.returncode:
                detail = summarize(out.stdout + out.stderr)
                break
        else:
            lock = tomllib.loads((path / 'Cargo.lock').read_text())
            bevies = {p.get('source') for p in lock['package'] if p['name'] == 'bevy'}
            detail = f'ok (rustc {rust})' if len(bevies) == 1 else \
                f'two Bevy copies in the graph: {sorted(bevies)}'
        ok = detail.startswith('ok')
        results[name] = (ok, detail)
        if not quiet:
            print(f'  {"PASS" if ok else "FAIL"} {name}: {detail}')
    return results


def all_probes(fork_files):
    return [physics_probe()] + [forks_probe(f) for f in fork_files]


def ceiling(frm, to, fork_files):
    probes = all_probes(fork_files)
    revs = first_parent(frm, to)
    print(f'Probing {to[:9]} (tip of the range):')
    if all(ok for ok, _ in probe(to, probes).values()):
        print(f'\nCeiling: {describe(to)}  -- the whole range builds.')
        return
    print(f'Probing {frm[:9]} (the current pin):')
    if not all(ok for ok, _ in probe(frm, probes).values()):
        sys.exit('The current pin itself fails; fix the probes or the forks before bisecting.')
    lo, hi = -1, len(revs) - 1   # revs[lo] (or frm) passes, revs[hi] fails
    while hi - lo > 1:
        mid = (lo + hi) // 2
        print(f'Probing {describe(revs[mid])}  [{hi - lo - 1} left]')
        if all(ok for ok, _ in probe(revs[mid], probes).values()):
            lo = mid
        else:
            hi = mid
    good = revs[lo] if lo >= 0 else frm
    print(f'\nCeiling: {describe(good)}\n     {good}')
    print(f'First failure: {describe(revs[hi])}')
    for name, (ok, detail) in probe(revs[hi], probes, quiet=True).items():
        if not ok:
            print(f'  {name}: {detail}')
    print(f'Then: cargo update -p bevy --precise {good} in each workspace (docs/upgrading-bevy.md).')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('command', choices=('walls', 'probe', 'ceiling'))
    parser.add_argument('rev', nargs='?')
    parser.add_argument('--from', dest='frm')
    parser.add_argument('--to')
    parser.add_argument('--forks', action='append', default=[], metavar='FILE',
                        help="a game's bevy_main_forks.json (repeatable)")
    args = parser.parse_args()
    fetch_bevy()
    frm = bevy('rev-parse', args.frm or locked_bevy())
    to = bevy('rev-parse', args.to or 'main')
    if args.command == 'walls':
        print_walls(frm, to)
    elif args.command == 'probe':
        if not args.rev:
            parser.error('probe needs a Bevy revision')
        print(f'Probing {describe(args.rev)}:')
        results = probe(args.rev, all_probes(args.forks))
        sys.exit(0 if all(ok for ok, _ in results.values()) else 1)
    else:
        ceiling(frm, to, args.forks)


if __name__ == '__main__':
    main()
