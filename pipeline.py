#!/usr/bin/env python3
"""Run the whole Second Opinion pipeline, skipping stages that are already done.

Each stage is a separate process that runs an existing script through its own
command line: download -> prepare -> verify -> detect (per group) -> forest (per
group) -> optional synthetic faults (per group). A stage is skipped when its
output is complete and nothing it depends on has changed: its script, its
arguments and every upstream stage are fingerprinted in a state file. Existing
outputs are never deleted; an output that must be redone is moved aside first.

    python3 pipeline.py --plan                 # show what would run or be skipped
    python3 pipeline.py                        # run everything that is not done
    python3 pipeline.py --smoke 30             # quick run on 30 points per group
    python3 pipeline.py --groups influent_volume --with-faults
    python3 pipeline.py --force detect         # redo all detector stages and downstream

Outputs and logs are private partner-derived data under data/tai/; keep them out of Git.
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'tai'
SCRIPTS = {
    'download': ROOT / 'data' / 'download.py',
    'prepare': ROOT / 'data' / 'tai_work' / 'scripts' / 'tai_pipeline.py',
    'verify': ROOT / 'data' / 'tai_work' / 'scripts' / 'tai_verify.py',
    'detect': ROOT / 'history_detector' / 'history_detector.py',
    'forest': ROOT / 'isolation_forest' / 'model.py',
    'faults': ROOT / 'history_detector' / 'synthetic_faults.py',
}
GROUPS = ('influent_volume', 'oxygen', 'ammonium')
TABLES = ('Installations', 'MeasurementPoints', 'MeasurementValues')


@dataclass
class Stage:
    name: str
    script: Path
    args: list[str]
    output: Path | None
    done: Callable[[], bool]
    needs: list[str] = field(default_factory=list)
    # Files whose contents decide whether an earlier result is still valid.
    code: list[Path] = field(default_factory=list)
    # A complete output with no recorded run (made before this driver) is accepted.
    adoptable: bool = False
    # The stage refuses a nonempty output directory, so a redo moves it aside first.
    fresh_output: bool = True


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def extracted_done(raw: Path) -> bool:
    return all((raw / table).is_dir() and any((raw / table).glob('*.csv.gz')) for table in TABLES)


def prepared_done(prepared: Path) -> bool:
    summary = read_json(prepared / 'summary.json')
    return (summary is not None and summary.get('file_limit_per_table') is None
            and (prepared / 'point_metadata.csv.gz').is_file()
            and (prepared / 'cleaned' / 'MeasurementValues').is_dir())


def marked_done(folder: Path, files: list[str], statuses: tuple[str, ...]) -> bool:
    info = read_json(folder / files[0])
    return (info is not None and info.get('status') in statuses
            and all((folder / name).is_file() for name in files[1:]))


def build_stages(root: Path, groups: list[str], smoke: int | None, with_faults: bool,
                 target_flag_rate: float, fault_sample: int) -> list[Stage]:
    """Describe every stage, its command-line arguments, output and completion check."""
    raw, prepared = DATA / 'extracted', DATA / 'prepared_history'
    partial = ['--max-points', str(smoke)] if smoke else []
    detector_status = ('smoke_run_partial',) if smoke else ('provisional_unvalidated',)
    stages = [
        Stage('download', SCRIPTS['download'], ['tai'], raw, lambda: extracted_done(raw),
              adoptable=True, fresh_output=False),
        Stage('prepare', SCRIPTS['prepare'], ['--raw', str(raw), '--output', str(prepared)], prepared,
              lambda: prepared_done(prepared), needs=['download'], code=[SCRIPTS['prepare']], adoptable=True),
        # Verification writes nothing; its recorded run is its completion marker.
        Stage('verify', SCRIPTS['verify'], [str(prepared)], None, lambda: True,
              needs=['prepare'], code=[SCRIPTS['verify']], fresh_output=False),
    ]
    for group in groups:
        history, forest, faults = root / f'history_{group}', root / f'forest_{group}', root / f'faults_{group}'
        stages.append(Stage(
            f'detect:{group}', SCRIPTS['detect'],
            ['--prepared', str(prepared), '--output', str(history), '--measurement', group,
             '--target-flag-rate', str(target_flag_rate), *partial],
            history, lambda h=history: marked_done(h, ['run_info.json', 'history_scores.csv.gz', 'cases.csv.gz'],
                                                   detector_status),
            needs=['verify'], code=[SCRIPTS['detect']]))
        stages.append(Stage(
            f'forest:{group}', SCRIPTS['forest'], ['--history-dir', str(history), '--output', str(forest)],
            forest, lambda f=forest: marked_done(f, ['run_info.json', 'scored_records.csv.gz'],
                                                 ('provisional_unvalidated',)),
            needs=[f'detect:{group}'], code=[SCRIPTS['forest']]))
        if with_faults:
            stages.append(Stage(
                f'faults:{group}', SCRIPTS['faults'],
                ['--prepared', str(prepared), '--output', str(faults), '--measurement', group,
                 '--sample', str(fault_sample), '--target-flag-rate', str(target_flag_rate), *partial],
                faults, lambda f=faults: marked_done(f, ['summary.json', 'injections.csv'],
                                                     ('smoke_run_partial',) if smoke else ('synthetic_faults_only',)),
                needs=['verify'], code=[SCRIPTS['faults'], SCRIPTS['detect']]))
    return stages


def fingerprint(stage: Stage, upstream: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path in stage.code:
        digest.update(path.read_bytes())
    digest.update(json.dumps(stage.args).encode())
    for name in stage.needs:
        digest.update(upstream[name].encode())
    return digest.hexdigest()


def state_key(stage: Stage) -> str:
    # Shared stages (download, prepare, verify) have one entry; per-run stages differ by output.
    return stage.name if stage.output is None else f'{stage.name}|{stage.output}'


def plan(stages: list[Stage], state: dict, forced: list[str]) -> list[tuple[Stage, str, str]]:
    """Decide for each stage: skip, adopt or run, with the reason."""
    decisions, prints, running = [], {}, set()
    for stage in stages:
        prints[stage.name] = fingerprint(stage, prints)
        entry = state.get(state_key(stage))
        complete = stage.done()
        is_forced = any(stage.name == f or stage.name.startswith(f + ':') for f in forced)
        if is_forced:
            action, reason = 'run', 'forced'
        elif running.intersection(stage.needs):
            action, reason = 'run', 'an upstream stage runs'
        elif complete and entry and entry.get('fingerprint') == prints[stage.name]:
            action, reason = 'skip', 'already done'
        elif complete and not entry and stage.adoptable:
            action, reason = 'adopt', 'complete output from before this driver'
        elif complete and entry:
            action, reason = 'run', 'code, settings or inputs changed'
        elif complete:
            action, reason = 'run', 'no recorded run for this output'
        else:
            action, reason = 'run', 'not done yet'
        if action == 'run':
            running.add(stage.name)
        decisions.append((stage, action, reason))
    return decisions


def move_aside(output: Path) -> Path | None:
    """Keep a previous output under a timestamped name instead of deleting it."""
    if not output.exists() or not any(output.iterdir()):
        return None
    stamp, counter = f'{datetime.now():%Y%m%d-%H%M%S}', 0
    target = output.with_name(f'{output.name}.old-{stamp}')
    while target.exists():
        counter += 1
        target = output.with_name(f'{output.name}.old-{stamp}-{counter}')
    output.rename(target)
    return target


def run_stage(stage: Stage, logs: Path) -> float:
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f"{stage.name.replace(':', '_')}.log"
    if stage.output is not None and stage.fresh_output:
        moved = move_aside(stage.output)
        if moved:
            print(f'    previous output kept at {moved}', flush=True)
    start = time.monotonic()
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run([sys.executable, '-B', str(stage.script), *stage.args],
                                cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise SystemExit(f'{stage.name} failed (exit {result.returncode}); see {log}')
    if not stage.done():
        raise SystemExit(f'{stage.name} finished but its output is incomplete; see {log}')
    return time.monotonic() - start


def execute(stages: list[Stage], state_path: Path, forced: list[str], dry_run: bool,
            logs: Path | None = None) -> list[tuple[str, str, str]]:
    state = read_json(state_path) or {}
    logs = logs or state_path.parent / 'logs'
    decisions = plan(stages, state, forced)
    prints = {}
    report = []
    for stage, action, reason in decisions:
        prints[stage.name] = fingerprint(stage, prints)
        print(f'{stage.name:24s} {action:6s} ({reason})', flush=True)
        if dry_run:
            report.append((stage.name, action, reason))
            continue
        if action == 'run':
            seconds = run_stage(stage, logs)
            reason = f'{reason}; {seconds:.0f}s'
            print(f'    done in {seconds:.0f}s', flush=True)
        if action in ('run', 'adopt'):
            state[state_key(stage)] = {'fingerprint': prints[stage.name], 'finished': datetime.now().isoformat(timespec='seconds'),
                                 'args': stage.args, 'output': None if stage.output is None else str(stage.output)}
            state_path.parent.mkdir(parents=True, exist_ok=True)
            # Written after every stage, so an interrupted run resumes where it stopped.
            state_path.write_text(json.dumps(state, indent=2), encoding='utf-8')
        report.append((stage.name, action, reason))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--groups', nargs='+', choices=GROUPS, default=list(GROUPS))
    parser.add_argument('--smoke', type=int, metavar='N', help='Quick run on the first N points per group')
    parser.add_argument('--with-faults', action='store_true', help='Also run the slow synthetic-fault comparison')
    parser.add_argument('--fault-sample', type=int, default=100, help='Series per group for the fault comparison')
    parser.add_argument('--target-flag-rate', type=float, default=0.01)
    parser.add_argument('--force', nargs='+', default=[], metavar='STAGE',
                        help='Redo these stages (e.g. prepare, detect, forest:oxygen) and everything downstream')
    parser.add_argument('--plan', action='store_true', help='Show what would run or be skipped, then stop')
    args = parser.parse_args()
    if args.smoke is not None and args.smoke < 1:
        parser.error('--smoke must be positive')
    root = DATA / (f'pipeline_smoke{args.smoke}' if args.smoke else 'pipeline')
    stages = build_stages(root, args.groups, args.smoke, args.with_faults, args.target_flag_rate, args.fault_sample)
    known = {stage.name for stage in stages} | {stage.name.split(':')[0] for stage in stages}
    unknown = [name for name in args.force if name not in known]
    if unknown:
        parser.error(f'unknown stage(s) {unknown}; choose from {sorted(known)}')
    print(f'Pipeline outputs: {root}', flush=True)
    # One state file for all runs, so smoke and full runs share download, prepare and verify.
    execute(stages, DATA / 'pipeline_state.json', args.force, args.plan, logs=root / 'logs')
    print('Plan only; nothing was run.' if args.plan else 'Pipeline complete. Outputs are private and provisional.')


if __name__ == '__main__':
    main()
