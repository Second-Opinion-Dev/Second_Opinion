"""Local-only Second Opinion web server with a streaming SQLite results index."""
from __future__ import annotations
import csv, gzip, hashlib, json, math, os, sqlite3, sys, threading, time
from datetime import date as calendar_date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'dashboard'))
from claude_assistant import explain_with_claude

WEB = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'tai'
DB = DATA / 'second_opinion_web_index.sqlite'
METRICS = ('influent_volume','oxygen','ammonium','nitrate','suspended_solids','temperature')
FIELDS = ('InstallationCodeOrigin','MeasurementPointID','ProcessCode','SubProcessCodeOrigin','SubProcessDescription','Product','ProductBalance','InstallationCodeDestination','SubProcessDestination','Unit','parsed_date','parsed_value','source_file','source_row','ai_status','ai_score','ai_flag','history_median','history_mad','history_scale','history_days','anomaly_score','signed_deviation_log','day_change_log','prior_deviation_log_mean','relative_level_log','is_zero','repeat_days_log')
state = {'phase':'idle','message':'','processed':0,'skipped':0,'total':None,'metrics':[], 'errors':[]}
lock = threading.Lock()

def number(s):
    try:
        n = float(s)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError): return None

def init_db(path):
    db = sqlite3.connect(path)
    db.executescript('''PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS readings
    (id TEXT PRIMARY KEY, metric TEXT NOT NULL, plant TEXT NOT NULL, point TEXT NOT NULL, date TEXT NOT NULL,
     value REAL, unit TEXT, score REAL, flag INTEGER, source_file TEXT, source_row TEXT, details TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS runs (metric TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, threshold REAL NOT NULL, status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS plants (code TEXT PRIMARY KEY, name TEXT);
    CREATE INDEX IF NOT EXISTS idx_readings_filter ON readings(plant,metric,date,point);
    CREATE INDEX IF NOT EXISTS idx_readings_flags ON readings(plant,metric,flag,date,score);''')
    return db

def fingerprint(paths):
    return '|'.join(f'{p.resolve()}:{p.stat().st_mtime_ns}:{p.stat().st_size}' for p in paths)

def manifest_total(root):
    """Return the recorded input-row count if each available run reports splits."""
    total, seen = 0, False
    for metric in METRICS:
        path = Path(root)/f'forest_{metric}'/'run_info.json'
        if not path.is_file(): continue
        try:
            counts = json.loads(path.read_text(encoding='utf-8')).get('split_counts')
            if not isinstance(counts, dict) or not counts: return None
            total += sum(int(n) for n in counts.values()); seen = True
        except (OSError, ValueError, TypeError, json.JSONDecodeError): return None
    return total if seen else None

def build_index(root, catalog_root=None, db_path=DB):
    """Stream each compressed file; incomplete or mismatched metrics are not shown."""
    root = Path(root); Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db = init_db(db_path)
    with lock: state.update(phase='indexing',processed=0,skipped=0,total=manifest_total(root),metrics=[],errors=[],message='')
    dropped_indexes = False
    try:
        db.execute('DELETE FROM plants'); db.commit()
        if catalog_root:
            try:
                names = {}
                for path in sorted((Path(catalog_root)/'Installations').glob('*.csv.gz')):
                    with gzip.open(path,'rt',encoding='utf-8',errors='replace',newline='') as f:
                        for row in csv.DictReader(f):
                            code = (row.get('Installation') or '').strip()
                            if code: names[code] = (row.get('Installation Description') or '').strip()
                if not names: raise ValueError('No installation records found')
                db.executemany('INSERT OR REPLACE INTO plants VALUES (?,?)', names.items()); db.commit()
            except (OSError, ValueError, KeyError) as exc:
                with lock: state['errors'].append('catalog: '+str(exc))
        for metric in METRICS:
            forest = root / f'forest_{metric}'; hist = root / f'history_{metric}'
            paths = [forest/'run_info.json', hist/'run_info.json', forest/'scored_records.csv.gz']
            if not all(p.is_file() for p in paths):
                db.execute('DELETE FROM readings WHERE metric=?',(metric,)); db.execute('DELETE FROM runs WHERE metric=?',(metric,)); db.commit()
                with lock: state['errors'].append(f'{metric}: unavailable')
                continue
            try:
                info = json.loads(paths[0].read_text(encoding='utf-8')); history = json.loads(paths[1].read_text(encoding='utf-8'))
                if info.get('measurement') != metric or history.get('measurement') != metric or info.get('status') != 'provisional_unvalidated' or history.get('status') not in ('provisional_unvalidated','smoke_run_partial'):
                    raise ValueError('incompatible or incomplete run')
                threshold = number(info.get('threshold'))
                if threshold is None: raise ValueError('missing threshold')
                fp = fingerprint(paths)
                current = db.execute('SELECT fingerprint FROM runs WHERE metric=?',(metric,)).fetchone()
                if current and current[0] == fp:
                    with lock:
                        state['metrics'].append(metric)
                        state['processed'] += sum(int(v) for v in (info.get('split_counts') or {}).values())
                    continue
                if not dropped_indexes:
                    db.execute('DROP INDEX IF EXISTS idx_readings_filter')
                    db.execute('DROP INDEX IF EXISTS idx_readings_flags')
                    db.commit(); dropped_indexes = True
                db.execute('BEGIN'); db.execute('DELETE FROM readings WHERE metric=?',(metric,)); db.execute('DELETE FROM runs WHERE metric=?',(metric,))
                batch=[]
                with gzip.open(paths[2], 'rt', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    required = {'InstallationCodeOrigin','MeasurementPointID','parsed_date','parsed_value','Unit','source_file','source_row','ai_status','ai_score','ai_flag','history_median','score_status','review_flag'}
                    if not required.issubset(reader.fieldnames or []): raise ValueError('missing required columns')
                    for row in reader:
                        plant,point,date,source_file,source_row = (row.get(x,'') or '' for x in ('InstallationCodeOrigin','MeasurementPointID','parsed_date','source_file','source_row'))
                        try:
                            if not plant or not point or not date or not source_file or not source_row: raise ValueError('missing provenance')
                            calendar_date.fromisoformat(date[:10])
                        except ValueError:
                            with lock: state['skipped'] += 1
                            continue
                        score, value = number(row.get('ai_score')), number(row.get('parsed_value'))
                        eligible = row.get('ai_status') == 'eligible' and value is not None and score is not None
                        flag_raw = (row.get('ai_flag') or '').strip().lower()
                        if eligible and (flag_raw not in ('true','false','1','0') or (flag_raw in ('true','1')) != (score >= threshold)): raise ValueError('flag and threshold disagree')
                        flag = int(flag_raw in ('true','1')) if eligible else None
                        key = hashlib.sha256(f'{metric}\0{source_file}\0{source_row}'.encode()).hexdigest()[:20]
                        detail = {k:row.get(k) for k in FIELDS if row.get(k) not in (None,'')}
                        batch.append((key,metric,plant,point,date[:10],value,row.get('Unit',''),score,flag,source_file,source_row,json.dumps(detail,ensure_ascii=False)))
                        if len(batch) >= 4000:
                            db.executemany('INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',batch)
                            with lock: state['processed'] += len(batch)
                            batch=[]
                    if batch:
                        db.executemany('INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',batch)
                        with lock: state['processed'] += len(batch)
                db.execute('INSERT INTO runs VALUES (?,?,?,?)',(metric,fp,threshold,info.get('status'))); db.commit()
                with lock: state['metrics'].append(metric)
            except (OSError,ValueError,sqlite3.Error,json.JSONDecodeError) as exc:
                db.rollback()
                db.execute('DELETE FROM readings WHERE metric=?',(metric,)); db.execute('DELETE FROM runs WHERE metric=?',(metric,)); db.commit()
                with lock: state['errors'].append(f'{metric}: {str(exc)}')
        if dropped_indexes:
            with lock: state['message'] = 'building_indexes'
            db.execute('CREATE INDEX IF NOT EXISTS idx_readings_filter ON readings(plant,metric,date,point)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_readings_flags ON readings(plant,metric,flag,date,score)')
            db.commit()
        with lock: state['phase'] = 'ready'
    except Exception as exc:
        with lock: state.update(phase='error',message=str(exc))
    finally: db.close()

def database():
    db = sqlite3.connect(DB,timeout=10); db.row_factory = sqlite3.Row; return db

def as_record(row):
    d=dict(row); d['details']=json.loads(d['details']); return d

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send_json(self, obj, code=200):
        body=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode('utf-8'); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path in ('/','/app.js','/style.css'):
            path=WEB/('index.html' if u.path=='/' else u.path[1:]); body=path.read_bytes()
            self.send_response(200); self.send_header('Content-Type',{'html':'text/html','js':'text/javascript','css':'text/css'}[path.suffix[1:]]+'; charset=utf-8'); self.end_headers(); self.wfile.write(body); return
        if u.path=='/api/status':
            with lock: self.send_json(dict(state)); return
        if not DB.exists() or state['phase'] != 'ready': self.send_json({'error':'Results not connected'},503); return
        try:
            db=database()
            if u.path=='/api/catalog':
                plants=[dict(r) for r in db.execute('SELECT plant AS code, COALESCE(MAX(name),\'\') AS name FROM (SELECT plant, NULL AS name FROM readings UNION ALL SELECT code AS plant, name FROM plants) GROUP BY plant ORDER BY plant')]
                metrics=[dict(r) for r in db.execute('SELECT metric,threshold,status FROM runs')]
                bounds=dict(db.execute('SELECT MIN(date) AS start, MAX(date) AS end FROM readings').fetchone())
                self.send_json({'plants':plants,'metrics':metrics,'bounds':bounds}); db.close(); return
            if u.path=='/api/readings':
                plant=q.get('plant',[''])[0]; metric=q.get('metric',[''])[0]; start=q.get('start',['0000-01-01'])[0]; end=q.get('end',['9999-12-31'])[0]; point=q.get('point',[''])[0]
                if metric not in METRICS or not plant: self.send_json({'error':'Select plant and metric'},400); return
                flags_only=q.get('flags',['0'])[0]=='1'
                where=' WHERE plant=? AND metric=? AND date BETWEEN ? AND ?'+(' AND point=?' if point else '')
                params=(plant,metric,start,end)+( (point,) if point else () )
                sql='SELECT * FROM readings'+where+(' AND flag=1 ORDER BY score DESC, date DESC, id' if flags_only else ' ORDER BY date DESC, point, id')+' LIMIT 500'
                try: offset=max(0,min(int(q.get('offset',['0'])[0]),10000000))
                except ValueError: offset=0
                rows=db.execute(sql+' OFFSET ?',params+(offset,)).fetchall()
                counts=dict(db.execute('SELECT COUNT(*) AS total, SUM(flag=1) AS flagged, SUM(flag IS NOT NULL) AS assessed, SUM(flag IS NULL) AS unassessed FROM readings'+where,params).fetchone())
                self.send_json({'rows':[as_record(r) for r in rows],'counts':counts,'limit':500,'offset':offset}); db.close(); return
            if u.path=='/api/points':
                metric=q.get('metric',[''])[0]; plant=q.get('plant',[''])[0]
                if metric not in METRICS: self.send_json({'error':'Select a metric'},400); return
                points=[r[0] for r in db.execute('SELECT DISTINCT point FROM readings WHERE plant=? AND metric=? ORDER BY point',(plant,metric))]
                self.send_json({'points':points}); db.close(); return
            if u.path=='/api/case':
                row=db.execute('SELECT * FROM readings WHERE id=? AND flag=1',(q.get('id',[''])[0],)).fetchone()
                if not row: self.send_json({'error':'Case not found'},404); return
                case=as_record(row); details=case['details']; start=(__import__('datetime').date.fromisoformat(case['date'])-__import__('datetime').timedelta(days=28)).isoformat()
                candidates=db.execute('SELECT * FROM readings WHERE plant=? AND metric=? AND point=? AND unit=? AND date BETWEEN ? AND ? ORDER BY date',(case['plant'],case['metric'],case['point'],case['unit'],start,case['date'])).fetchall()
                context=('ProcessCode','SubProcessCodeOrigin','Product','ProductBalance','InstallationCodeDestination','SubProcessDestination')
                history=[x for x in map(as_record,candidates) if all(x['details'].get(k,'')==details.get(k,'') for k in context)]
                run=dict(db.execute('SELECT threshold,status FROM runs WHERE metric=?',(case['metric'],)).fetchone())
                self.send_json({'case':case,'history':history,'run':run}); db.close(); return
            self.send_json({'error':'Not found'},404); db.close()
        except (sqlite3.Error,ValueError) as exc: self.send_json({'error':str(exc)},500)
    def do_POST(self):
        origin=self.headers.get('Origin','')
        if origin and origin != f'http://127.0.0.1:{PORT}': self.send_json({'error':'Invalid origin'},403); return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length > 16384: self.send_json({'error':'Request too large'},413); return
            body=json.loads(self.rfile.read(length) or b'{}')
            if self.path=='/api/connect':
                root=Path(str(body.get('path',''))).expanduser()
                if not root.is_absolute(): root=ROOT/root
                if not root.is_dir(): self.send_json({'error':'Folder not found'},400); return
                cat_text=str(body.get('catalog','')).strip(); cat_path=None
                if cat_text:
                    cat_path=Path(cat_text).expanduser(); cat_path=cat_path if cat_path.is_absolute() else ROOT/cat_path
                    if not cat_path.is_dir(): self.send_json({'error':'Plant catalogue folder not found'},400); return
                with lock:
                    if state['phase']=='indexing': self.send_json({'error':'Indexing already in progress'},409); return
                    state['phase']='indexing'
                threading.Thread(target=build_index,args=(root,cat_path),daemon=True).start(); self.send_json({'ok':True}); return
            if self.path=='/api/assistant':
                if body.get('consent') is not True: self.send_json({'error':'Permission required'},403); return
                db=database(); row=db.execute('SELECT * FROM readings WHERE id=? AND flag=1',(str(body.get('id','')),)).fetchone()
                if not row: self.send_json({'error':'Case not found'},404); return
                case=as_record(row); threshold=db.execute('SELECT threshold FROM runs WHERE metric=?',(case['metric'],)).fetchone()[0]; db.close()
                evidence={'plant':case['plant'],'point':case['point'],'date':case['date'],'metric':case['metric'],'value':case['value'],'unit':case['unit'],'model_score':case['score'],'model_threshold':threshold,'details':{k:v for k,v in case['details'].items() if k not in ('source_file','source_row')}}
                reply=explain_with_claude(evidence,str(body.get('question',''))[:2000],str(body.get('language','English')),consent=True)
                self.send_json({'reply':reply}); return
            self.send_json({'error':'Not found'},404)
        except (ValueError,PermissionError,RuntimeError,sqlite3.Error,json.JSONDecodeError) as exc: self.send_json({'error':str(exc)},400)

PORT = int(os.environ.get('SECOND_OPINION_PORT','8518'))
if __name__ == '__main__':
    print(f'Second Opinion: http://127.0.0.1:{PORT}', flush=True)
    ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
