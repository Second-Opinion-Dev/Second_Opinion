import csv, gzip, json, sqlite3, tempfile, unittest, threading
from urllib.request import urlopen
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from contextlib import closing
import server


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.db=self.root/'index.sqlite'
        (self.root/'forest_oxygen').mkdir(); (self.root/'history_oxygen').mkdir()
        (self.root/'forest_oxygen/run_info.json').write_text(json.dumps({'status':'provisional_unvalidated','measurement':'oxygen','threshold':0.6}))
        (self.root/'history_oxygen/run_info.json').write_text(json.dumps({'status':'provisional_unvalidated','measurement':'oxygen'}))
        self.path=self.root/'forest_oxygen/scored_records.csv.gz'
        self.rows=[dict(InstallationCodeOrigin='test-plant',MeasurementPointID='test-point',ProcessCode='test',Unit='mg/l',parsed_date='2025-01-01',parsed_value='2',source_file='test',source_row='1',ai_status='eligible',ai_score='0.7',ai_flag='True',history_median='1.5',score_status='scored',review_flag='True'),dict(InstallationCodeOrigin='test-plant',MeasurementPointID='test-point',ProcessCode='test',Unit='mg/l',parsed_date='2025-01-02',parsed_value='3',source_file='test',source_row='2',ai_status='ineligible',ai_score='',ai_flag='',history_median='',score_status='unscored',review_flag='')]
        self.write()
    def tearDown(self): self.tmp.cleanup()
    def write(self):
        with gzip.open(self.path,'wt',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=self.rows[0].keys()); w.writeheader(); w.writerows(self.rows)
    def test_stream_index_and_unassessed(self):
        server.build_index(self.root,db_path=self.db)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('select flag from readings order by date').fetchall(),[(1,),(None,)])
            self.assertEqual(db.execute('select metric from runs').fetchone()[0],'oxygen')
        self.assertEqual(server.state['phase'],'ready')
    def test_wrong_flag_discards_metric(self):
        self.rows[0]['ai_flag']='False'; self.write(); server.build_index(self.root,db_path=self.db)
        with closing(sqlite3.connect(self.db)) as db: self.assertEqual(db.execute('select count(*) from readings').fetchone()[0],0)
        self.assertTrue(any('threshold' in x for x in server.state['errors']))
    def test_manifest_total_and_completed_index(self):
        path = self.root/'forest_oxygen/run_info.json'
        info=json.loads(path.read_text()); info['split_counts']={'train':1,'test':1}
        path.write_text(json.dumps(info))
        self.assertEqual(server.manifest_total(self.root),2)
        server.build_index(self.root,db_path=self.db)
        self.assertEqual(server.state['total'],2)
        self.assertEqual(server.state['processed']+server.state['skipped'],2)
        server.build_index(self.root,db_path=self.db)
        self.assertEqual(server.state['processed'],2)
    def test_readonly_index_reuses_only_matching_source(self):
        server.build_index(self.root,db_path=self.db)
        with patch.object(server,'init_db',side_effect=sqlite3.OperationalError('attempt to write a readonly database')):
            server.build_index(self.root,db_path=self.db)
            self.assertEqual(server.state['phase'],'ready')
            self.assertTrue(server.state['read_only'])
            self.assertEqual(server.state['metrics'],['oxygen'])
            self.rows[0]['parsed_value']='7'; self.write()
            server.build_index(self.root,db_path=self.db)
            self.assertEqual(server.state['phase'],'error')
    def test_claude_requires_consent(self):
        with self.assertRaises(PermissionError): server.explain_with_claude({},'', 'English', consent=False)
    def test_dashboard_port_is_exclusive(self):
        first=server.LocalServer(('127.0.0.1',0),server.Handler)
        try:
            with self.assertRaises(OSError): server.LocalServer(('127.0.0.1',first.server_port),server.Handler)
        finally: first.server_close()
    def test_local_api_case_and_readings(self):
        server.build_index(self.root,db_path=self.db)
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True); thread.start()
        try:
            with patch.object(server,'DB',self.db):
                base=f'http://127.0.0.1:{http.server_port}'
                with urlopen(base+'/api/catalog') as r: catalog=json.load(r)
                self.assertEqual(catalog['plants'][0]['code'],'test-plant')
                with urlopen(base+'/favicon.ico') as r: self.assertEqual(r.status,200)
                with urlopen(base+'/api/points?'+urlencode({'plant':'test-plant','metric':'oxygen'})) as r: points=json.load(r)
                self.assertEqual(points['points'],['test-point'])
                with urlopen(base+'/api/readings?'+urlencode({'plant':'test-plant','metric':'oxygen','flags':'1'})) as r: readings=json.load(r)
                self.assertEqual(readings['counts']['flagged'],1)
                with urlopen(base+'/api/case?'+urlencode({'id':readings['rows'][0]['id']})) as r: case=json.load(r)
                self.assertEqual(case['case']['point'],'test-point')
                self.assertEqual(case['run']['threshold'],0.6)
        finally:
            http.shutdown(); http.server_close(); thread.join()

    def test_all_metrics_include_only_available_groups_and_order_flags_by_date(self):
        server.build_index(self.root,db_path=self.db)
        with closing(sqlite3.connect(self.db)) as db:
            row=db.execute('SELECT * FROM readings WHERE flag=1').fetchone()
            second=list(row); second[0]='second'; second[1]='ammonium'; second[4]='2025-01-03'; second[7]=0.1
            db.execute('INSERT INTO readings VALUES ('+','.join('?' for _ in second)+')',second)
            db.commit()
        server.state['metrics']=['oxygen','ammonium']
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            with patch.object(server,'DB',self.db):
                base=f'http://127.0.0.1:{http.server_port}'
                with urlopen(base+'/api/readings?'+urlencode({'plant':'test-plant','metric':'all','flags':'1'})) as r: result=json.load(r)
                self.assertEqual([row['metric'] for row in result['rows']],['ammonium','oxygen'])
                with urlopen(base+'/api/points?'+urlencode({'plant':'test-plant','metric':'all'})) as r: points=json.load(r)
                self.assertEqual(points['points'],['test-point'])
        finally:
            http.shutdown();http.server_close();thread.join()

    def test_readings_and_queue_paginate_without_losing_records(self):
        self.rows=[dict(self.rows[0], source_row=str(i), parsed_value=str(i)) for i in range(103)]
        self.write()
        server.build_index(self.root,db_path=self.db)
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True); thread.start()
        try:
            with patch.object(server,'DB',self.db):
                base=f'http://127.0.0.1:{http.server_port}/api/readings?'
                for flags in ('0','1'):
                    pages=[]
                    for offset in (0,50,100):
                        with urlopen(base+urlencode({'plant':'test-plant','metric':'oxygen','flags':flags,'offset':offset})) as response:
                            page=json.load(response)
                        self.assertEqual(page['limit'],50)
                        self.assertEqual(page['counts']['total'],103)
                        pages.append(page['rows'])
                    self.assertEqual([len(page) for page in pages],[50,50,3])
                    self.assertEqual(len({row['id'] for page in pages for row in page}),103)
        finally:
            http.shutdown(); http.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
