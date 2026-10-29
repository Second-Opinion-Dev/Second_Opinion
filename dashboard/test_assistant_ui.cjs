const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function makePage(fetchImpl) {
  const elements = new Map();
  function node(id) {
    return {
      id, value:'', _text:'', children:[], hidden:false, checked:false, disabled:false,
      get options(){return this.children},
      get textContent(){return this._text+this.children.map(child=>child.textContent).join('')},
      set textContent(value){this._text=value;this.children=[]},
      classList:{toggle() {}, contains(){return false}}, setAttribute(){}, addEventListener(){},
      replaceChildren(){this._text='';this.children=[]}, append(child){this.children.push(child)}, scrollIntoView() {}
    };
  }
  function element(id) {
    if (!elements.has(id)) elements.set(id, node(id));
    return elements.get(id);
  }
  const document = {getElementById:element, createElement:node, createTextNode(text){const n=node('#text');n.textContent=text;return n}, querySelectorAll:()=>[], documentElement:{}, body:{classList:{add(){},toggle(){},contains(){return false}}}};
  const context = vm.createContext({document,localStorage:{getItem(){return null},setItem(){}},fetch:fetchImpl,URLSearchParams,console,setTimeout});
  vm.runInContext(fs.readFileSync('dashboard/app.js','utf8'),context);
  vm.runInContext("current={case:{id:'fictional-case'}}",context);
  return {element,context};
}

test('permission error is shown beside the button and nothing is sent', async () => {
  let called=false;
  const page=makePage(async()=>{called=true;throw Error('should not send')});
  await page.element('ask').onclick();
  assert.equal(called,false);
  assert.match(page.element('askStatus').textContent,/confirm permission/i);
  assert.equal(page.element('askStatus').hidden,false);
});

test('filter submission accepts a displayed plant label and preserves its selected point', async () => {
  const requests=[];
  const page=makePage(async url=>{requests.push(url);return {ok:true,json:async()=>url.startsWith('/api/points')?{points:['point-1']}:{rows:[],counts:{total:0,flagged:0,assessed:0,unassessed:0}}}});
  vm.runInContext("catalog={plants:[{code:'NL.09.ZDR_',name:'RWZI Druten'}],metrics:[]}",page.context);
  page.element('plantSearch').value='RWZI Druten (NL.09.ZDR_)';
  page.element('plant').value='NL.09.ZDR_';
  page.element('metric').value='ammonium';
  page.element('point').value='point-1';
  await page.element('filters').onsubmit({preventDefault(){}});
  assert.ok(requests.some(url=>url.includes('/api/readings?')&&url.includes('point=point-1')));
});

test('assistant formatting is readable and treats HTML as text', async () => {
  const page=makePage(async()=>({ok:true,json:async()=>({reply:'**Where:** Plant A **When:** 2025-01-01\n\n- Check <script>alert(1)</script>\n- Review history'})}));
  page.element('consent').checked=true;
  await page.element('ask').onclick();
  const answer=page.element('answer');
  assert.deepEqual(answer.children.map(child=>child.id),['p','p','ul']);
  assert.ok(answer.children[0].children.some(child=>child.id==='strong'));
  assert.match(answer.textContent,/<script>alert\(1\)<\/script>/);
  assert.equal(answer.children[2].children.length,2);
});

test('escaped Markdown labels and point identifiers render cleanly', async () => {
  const page=makePage(async()=>({ok:true,json:async()=>({reply:'\\*\\*Where:\\*\\* 09.ZDR\\_point — \\*\\*When:\\*\\* 2026-01-01 — \\*\\*Why:\\*\\* Flagged for review.'})}));
  page.element('consent').checked=true;
  await page.element('ask').onclick();
  const answer=page.element('answer');
  assert.deepEqual(answer.children.map(child=>child.id),['p','p','p']);
  assert.equal(answer.textContent,'Where: 09.ZDR_pointWhen: 2026-01-01Why: Flagged for review.');
});

test('API errors and successful replies are visible beside the button', async () => {
  const fail=makePage(async()=>({ok:false,json:async()=>({error:'Set ANTHROPIC_API_KEY before starting the app.'})}));
  fail.element('consent').checked=true;
  await fail.element('ask').onclick();
  assert.match(fail.element('askStatus').textContent,/ANTHROPIC_API_KEY/);
  assert.equal(fail.element('ask').disabled,false);
  const success=makePage(async()=>({ok:true,json:async()=>({reply:'Review the measurement.'})}));
  success.element('consent').checked=true;
  await success.element('ask').onclick();
  assert.equal(success.element('answer').textContent,'Review the measurement.');
  assert.equal(success.element('answer').hidden,false);
});

test('all metrics clears the previous point and ignores an older readings response', async () => {
  let finishOld;
  const requests=[];
  const page=makePage(async url=>{
    requests.push(url);
    if(url.startsWith('/api/points'))return {ok:true,json:async()=>({points:['fictional-ammonium','fictional-oxygen']})};
    if(url.includes('metric=ammonium'))return new Promise(resolve=>{finishOld=()=>resolve({ok:true,json:async()=>({rows:[],counts:{total:0}})})});
    return {ok:true,json:async()=>({rows:[],counts:{total:12,assessed:12,flagged:1}})};
  });
  vm.runInContext("catalog={plants:[],metrics:[]}",page.context);
  page.element('plant').value='fictional-plant';
  page.element('metric').value='ammonium';
  page.element('point').value='old-point';
  const old=vm.runInContext('loadReadings()',page.context);
  page.element('metric').value='all';
  await page.element('metric').onchange();
  assert.equal(page.element('point').value,'');
  const query=new URLSearchParams(requests.at(-1).split('?')[1]);
  assert.equal(query.get('metric'),'all');
  assert.equal(query.get('point'),'');
  assert.equal(page.element('total').textContent,'12');
  finishOld();await old;
  assert.equal(page.element('total').textContent,'12');
});

test('an obsolete selection error cannot overwrite a successful all-metrics request', async () => {
  let finishOld;
  const requests=[];
  const page=makePage(async url=>{
    requests.push(url);
    if(url.startsWith('/api/points'))return {ok:true,json:async()=>({points:['fictional-ammonium','fictional-oxygen']})};
    if(url.includes('metric=ammonium'))return new Promise(resolve=>{finishOld=()=>resolve({ok:false,json:async()=>({error:'Select plant and available metric'})})});
    return {ok:true,json:async()=>({rows:[],counts:{total:12,assessed:12,flagged:1}})};
  });
  vm.runInContext("catalog={plants:[],metrics:[]}",page.context);
  page.element('plant').value='fictional-plant';
  page.element('metric').value='ammonium';
  page.element('point').value='old-point';
  const old=vm.runInContext('loadReadings()',page.context);
  page.element('metric').value='all';
  await page.element('metric').onchange();
  assert.equal(page.element('point').value,'');
  const query=new URLSearchParams(requests.at(-1).split('?')[1]);
  assert.equal(query.get('metric'),'all');
  assert.equal(query.get('point'),'');
  assert.equal(page.element('total').textContent,'12');
  finishOld();await old;
  assert.equal(page.element('error').hidden,true);
  assert.equal(page.element('total').textContent,'12');
});
