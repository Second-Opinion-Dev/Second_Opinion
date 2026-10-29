#!/usr/bin/env python3
"""Run the whole Second Opinion pipeline, skipping stages that are already done.

Each stage is a separate process that runs an existing script through its own
command line: prepare -> verify -> detect (per group) -> forest (per group) ->
dashboard index (full runs only), plus optional synthetic faults (per group).
The raw export must already be in
data/tai/extracted/ (Installations/, MeasurementPoints/, MeasurementValues/).
A stage is skipped when its output is complete and nothing it depends on has
changed: its script, its arguments and every upstream stage are fingerprinted in
a state file. Existing outputs are never deleted; an output that must be redone
is moved aside first.

    python3 src/pipeline.py --plan                 # show what would run or be skipped
    python3 src/pipeline.py                        # run everything that is not done
    python3 src/pipeline.py --smoke 30             # quick run on 30 points per group
    python3 src/pipeline.py --groups influent_volume --with-faults
    python3 src/pipeline.py --force detect         # redo all detector stages and downstream
    python3 src/pipeline.py --jobs 3               # run up to three independent stages at once
    python3 src/pipeline.py --workers 8            # clean up to eight files at once in the prepare stage

Outputs and logs are derived from private measurement data under data/tai/; keep them out of Git.
"""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable

from progress_bar import PROGRESS_FILE_ENV, Progress, bar_line, duration

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
DATA = ROOT / 'data' / 'tai'
SCRIPTS = {
    'prepare': SRC / 'data_prep' / 'tai_pipeline.py',
    'verify': SRC / 'data_prep' / 'tai_verify.py',
    'detect': SRC / 'history_detector' / 'history_detector.py',
    'forest': SRC / 'isolation_forest' / 'model.py',
    'faults': SRC / 'history_detector' / 'synthetic_faults.py',
    'index': SRC / 'dashboard_index.py',
}
DASHBOARD_SERVER = ROOT / 'dashboard' / 'server.py'
GROUPS = ('influent_volume', 'oxygen', 'ammonium', 'nitrate', 'suspended_solids', 'temperature')
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
    # Arguments that only change how fast the stage runs, so they stay out of the fingerprint.
    run_args: list[str] = field(default_factory=list)


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


def index_done(results: Path, groups: list[str]) -> bool:
    from dashboard_index import dashboard_server, is_current
    return is_current(results, dashboard_server().DB, groups)


def marked_done(folder: Path, files: list[str], statuses: tuple[str, ...]) -> bool:
    info = read_json(folder / files[0])
    return (info is not None and info.get('status') in statuses
            and all((folder / name).is_file() for name in files[1:]))


def build_stages(root: Path, groups: list[str], smoke: int | None, with_faults: bool,
                 target_flag_rate: float, fault_sample: int, workers: int = 1) -> list[Stage]:
    """Describe every stage, its command-line arguments, output and completion check."""
    raw, prepared = DATA / 'extracted', DATA / 'prepared_history'
    partial = ['--max-points', str(smoke)] if smoke else []
    detector_status = ('smoke_run_partial',) if smoke else ('provisional_unvalidated',)
    stages = [
        Stage('prepare', SCRIPTS['prepare'], ['--raw', str(raw), '--output', str(prepared)], prepared,
              lambda: prepared_done(prepared), code=[SCRIPTS['prepare']], adoptable=True,
              run_args=['--workers', str(workers)]),
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
    if not smoke:
        # The dashboard reads one shared index file, so only full runs refresh it;
        # the dashboard still indexes any other results folder when it connects.
        stages.append(Stage(
            'index', SCRIPTS['index'], ['--results', str(root), '--catalog', str(raw), '--measurement', *groups],
            None, lambda: index_done(root, groups), needs=[f'forest:{group}' for group in groups],
            code=[SCRIPTS['index'], DASHBOARD_SERVER], adoptable=True, fresh_output=False))
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
    # Shared stages (prepare, verify) have one entry; per-run stages differ by output.
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


def progress_file(stage: Stage, logs: Path) -> Path:
    return logs / f"{stage.name.replace(':', '_')}.progress.json"


def run_stage(stage: Stage, logs: Path, say: Callable[[str], None] = print) -> float:
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f"{stage.name.replace(':', '_')}.log"
    if stage.output is not None and stage.fresh_output:
        moved = move_aside(stage.output)
        if moved:
            say(f'    previous output kept at {moved}')
    # A stage that reports progress writes it here. An old report is removed when possible; on Windows
    # the driver may be reading it at this moment, and LiveStages ignores reports older than the stage anyway.
    report = progress_file(stage, logs)
    try:
        report.unlink(missing_ok=True)
    except PermissionError:
        pass
    start = time.monotonic()
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run([sys.executable, '-B', str(stage.script), *stage.args, *stage.run_args],
                                cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                env={**os.environ, PROGRESS_FILE_ENV: str(report)})
    if result.returncode != 0:
        raise SystemExit(f'{stage.name} failed (exit {result.returncode}); see {log}')
    if not stage.done():
        raise SystemExit(f'{stage.name} finished but its output is incomplete; see {log}')
    return time.monotonic() - start


class LiveStages:
    """What each stage of a run is doing, for the driver's status line.

    A running stage reports its progress to its progress_file; one that reports nothing still
    shows its time so far.
    """

    def __init__(self, decisions: list[tuple[Stage, str, str]], logs: Path):
        # Start of each running stage: monotonic for its duration, wall clock to compare with report files.
        self.logs, self.started, self.started_at = logs, {}, {}
        self.entries = [{'name': stage.name, 'action': action, 'state': 'pending' if action == 'run' else 'done',
                         'share': None, 'text': '', 'seconds': None} for stage, action, _ in decisions]
        self.by_name = {entry['name']: entry for entry in self.entries}
        self.stages = {stage.name: stage for stage, _, _ in decisions}

    def set(self, name: str, state: str, seconds: float | None = None) -> None:
        entry = self.by_name[name]
        entry['state'] = state
        if state == 'running':
            self.started[name], self.started_at[name] = time.monotonic(), time.time()
        if seconds is not None:
            entry['seconds'] = round(seconds, 1)
        if state == 'done':
            entry['share'] = 1.0

    def refresh(self) -> None:
        """Bring running stages up to date: their time so far and what they last reported."""
        for name, began in self.started.items():
            entry = self.by_name[name]
            if entry['state'] != 'running':
                continue
            entry['seconds'] = round(time.monotonic() - began, 1)
            path = progress_file(self.stages[name], self.logs)
            try:
                # A report from before this stage started belongs to an earlier run.
                current = path.stat().st_mtime >= self.started_at[name] - 1
            except OSError:
                current = False
            report = read_json(path) if current else None
            if report:
                entry['share'], entry['text'] = report.get('share'), report.get('text', '')


def overview(entries: list[dict], elapsed: float, width: int = 100) -> tuple[float, str]:
    """The driver's one status line, from LiveStages entries: the overall share and its text."""
    steps = [entry for entry in entries if entry['action'] == 'run']
    done = sum(entry['state'] == 'done' for entry in steps)
    running = [entry for entry in steps if entry['state'] == 'running']
    share = (done + sum(entry['share'] or 0 for entry in running)) / len(steps) if steps else 1.0
    if len(running) == 1 and running[0]['text']:
        # One stage at a time: its own progress line says the most.
        return share, f"[{done}/{len(steps)}] {running[0]['text']}"[:width]
    items = ', '.join(f"{entry['name']} {entry['share']:.0%}" if entry['share'] is not None
                      else f"{entry['name']} {duration(entry['seconds'] or 0)}" for entry in running)
    amount = f'{done}/{len(steps)} steps' + (f' · {items}' if items else '')
    # Stages differ widely in length, so no time left is estimated.
    return share, bar_line('Pipeline', share, amount, elapsed, width, estimate=False)


def execute(stages: list[Stage], state_path: Path, forced: list[str], dry_run: bool,
            logs: Path | None = None, jobs: int = 1) -> list[tuple[str, str, str]]:
    """Run the stages that need it, up to `jobs` at once, each after all stages it needs.

    Only this function writes the state file, so parallel stages cannot overwrite
    each other's records. If a stage fails, no new stage starts; running stages
    finish and are recorded, then the run stops with every failure listed.
    While it runs, one status line follows the running stages; messages print above it.
    """
    if jobs < 1:
        raise ValueError('jobs must be at least 1')
    state = read_json(state_path) or {}
    logs = logs or state_path.parent / 'logs'
    decisions = plan(stages, state, forced)
    prints = {}
    for stage in stages:
        prints[stage.name] = fingerprint(stage, prints)
    report = {stage.name: (action, reason) for stage, action, reason in decisions}
    for stage, action, reason in decisions:
        print(f'{stage.name:24s} {action:6s} ({reason})', flush=True)
    if dry_run:
        return [(stage.name, *report[stage.name]) for stage in stages]

    def record(stage: Stage) -> None:
        state[state_key(stage)] = {'fingerprint': prints[stage.name], 'finished': datetime.now().isoformat(timespec='seconds'),
                                   'args': stage.args, 'output': None if stage.output is None else str(stage.output)}
        state_path.parent.mkdir(parents=True, exist_ok=True)
        # Written after every stage, so an interrupted run resumes where it stopped.
        state_path.write_text(json.dumps(state, indent=2), encoding='utf-8')

    for stage, action, _ in decisions:
        if action == 'adopt':
            record(stage)
    finished = {stage.name for stage, action, _ in decisions if action != 'run'}
    pending = [stage for stage, action, _ in decisions if action == 'run']
    failures = []
    status = LiveStages(decisions, logs)
    line = Progress()

    def show() -> None:
        share, text = overview(status.entries, line.elapsed(), line.width())
        line.show(text, share=share)

    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            running = {}
            while pending or running:
                # Start, in pipeline order, every waiting stage whose inputs are finished.
                for stage in list(pending):
                    if failures or len(running) >= jobs:
                        break
                    if all(name in finished for name in stage.needs):
                        pending.remove(stage)
                        line.message(f'  started  {stage.name}')
                        running[pool.submit(run_stage, stage, logs, line.message)] = stage
                        status.set(stage.name, 'running')
                        show()
                if not running:
                    break
                # Wake at least every second to refresh the status line.
                done, _ = wait(running, timeout=1, return_when=FIRST_COMPLETED)
                status.refresh()
                show()
                for future in done:
                    stage = running.pop(future)
                    try:
                        seconds = future.result()
                    except (SystemExit, Exception) as error:
                        # Any error in starting or checking a stage fails that stage, not the whole driver,
                        # so stages already running still finish and are recorded.
                        if not isinstance(error, SystemExit):
                            error = SystemExit(f'{stage.name} failed: {type(error).__name__}: {error}')
                        failures.append(str(error))
                        status.set(stage.name, 'failed')
                        line.message(f'  FAILED   {stage.name}: {error}')
                        continue
                    finished.add(stage.name)
                    record(stage)
                    status.set(stage.name, 'done', seconds)
                    report[stage.name] = ('run', f'{report[stage.name][1]}; {seconds:.0f}s')
                    line.message(f'  finished {stage.name} in {seconds:.0f}s')
                    show()
    except BaseException:
        line.close()
        raise
    steps = sum(action == 'run' for _, action, _ in decisions)
    if failures:
        skipped = f'; {len(pending)} stage(s) not started' if pending else ''
        message = 'Pipeline stopped: ' + ' | '.join(failures) + skipped
        line.close(f'Pipeline stopped after {duration(line.elapsed())}')
        raise SystemExit(message)
    line.close(f'Pipeline ran {steps} steps in {duration(line.elapsed())}')
    return [(stage.name, *report[stage.name]) for stage in stages]


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
    parser.add_argument('--jobs', type=int, default=1, metavar='N',
                        help='Run up to N independent stages at once (each detector holds its group in memory)')
    parser.add_argument('--workers', type=int, default=1, metavar='N',
                        help='Clean up to N files at once inside the prepare stage; the output is identical to N=1')
    args = parser.parse_args()
    if args.smoke is not None and args.smoke < 1:
        parser.error('--smoke must be positive')
    if args.jobs < 1:
        parser.error('--jobs must be at least 1')
    if args.workers < 1:
        parser.error('--workers must be at least 1')
    root = DATA / (f'pipeline_smoke{args.smoke}' if args.smoke else 'pipeline')
    stages = build_stages(root, args.groups, args.smoke, args.with_faults, args.target_flag_rate, args.fault_sample,
                          args.workers)
    known = {stage.name for stage in stages} | {stage.name.split(':')[0] for stage in stages}
    unknown = [name for name in args.force if name not in known]
    if unknown:
        parser.error(f'unknown stage(s) {unknown}; choose from {sorted(known)}')
    if not extracted_done(DATA / 'extracted'):
        parser.error(f"no raw export found in {DATA / 'extracted'}; expected nonempty "
                     f"{', '.join(TABLES)} folders of .csv.gz files")
    print(f'Pipeline outputs: {root}', flush=True)
    # One state file for all runs, so smoke and full runs share prepare and verify.
    execute(stages, DATA / 'pipeline_state.json', args.force, args.plan, logs=root / 'logs', jobs=args.jobs)
    print('Plan only; nothing was run.' if args.plan else 'Pipeline complete. Outputs are private and provisional.')


if __name__ == '__main__':
    main()
