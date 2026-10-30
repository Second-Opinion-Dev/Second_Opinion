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
      classList:{names:new Set(), toggle() {}, contains(name){return this.names.has(name)}, add(name){this.names.add(name)}}, setAttribute(){}, removeAttribute(){}, select(){}, blur(){}, listeners:{}, addEventListener(type,fn){(this.listeners[type]=this.listeners[type]||[]).push(fn)},
      replaceChildren(...items){this._text='';this.children=items}, append(child){this.children.push(child)}, scrollIntoView() {}
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

test('changing either date refreshes the readings with that date and the selected point', async () => {
  const requests=[];
  const page=makePage(async url=>{requests.push(url);return {ok:true,json:async()=>({rows:[],counts:{total:0,flagged:0,assessed:0,unassessed:0}})}});
  vm.runInContext("catalog={plants:[{code:'NL.09.ZDR_',name:'RWZI Druten'}],metrics:[]}",page.context);
  page.element('plant').value='NL.09.ZDR_';
  page.element('metric').value='ammonium';
  page.element('point').value='point-1';
  page.element('start').value='2024-01-01';
  page.element('end').value='2024-12-31';
  await page.element('start').onchange();
  let query=new URLSearchParams(requests.at(-1).split('?')[1]);
  assert.equal(query.get('start'),'2024-01-01');assert.equal(query.get('point'),'point-1');
  page.element('end').value='2024-06-30';
  await page.element('end').onchange();
  query=new URLSearchParams(requests.at(-1).split('?')[1]);
  assert.equal(query.get('end'),'2024-06-30');
  const sent=requests.length;
  page.element('end').value='';
  await page.element('end').onchange();
  assert.equal(requests.length,sent);  // a cleared date does not refresh
});

test('choosing a navigation tab closes an open reading', () => {
  const page=makePage(async()=>({ok:true,json:async()=>({rows:[],counts:{}})}));
  page.element('casePanel').hidden=false;
  assert.ok(vm.runInContext("current!==null",page.context));
  vm.runInContext("setPage('queue')",page.context);
  assert.equal(page.element('casePanel').hidden,true);
  assert.equal(vm.runInContext("current",page.context),null);
  assert.equal(vm.runInContext("page",page.context),'queue');
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

test('provider selection sends request-scoped key and clears it without storing it', async () => {
  let sent;
  const page=makePage(async(url,options)=>{sent=JSON.parse(options.body);return {ok:true,json:async()=>({reply:'Check the records.'})}});
  page.element('aiProvider').value='openai';
  page.element('aiModel').value='test-model';
  page.element('aiKey').value='test-key';
  page.element('consent').checked=true;
  await page.element('ask').onclick();
  assert.equal(sent.provider,'openai');assert.equal(sent.model,'test-model');assert.equal(sent.api_key,'test-key');
  assert.equal(page.element('aiKey').value,'');
  page.element('aiKey').value='another-key';
  page.element('aiProvider').value='xai';
  page.element('aiProvider').onchange();
  assert.equal(page.element('aiKey').value,'');assert.equal(page.element('consent').checked,false);
});

const plants="catalog={plants:[{code:'P1',name:'First plant'},{code:'P2',name:'Second plant'},{code:'P3',name:'Third'}],metrics:[]};setPlant(catalog.plants[0]);filterPlants()";
const fire=(node,type,event={})=>node.listeners[type].forEach(fn=>fn({preventDefault(){},...event}));

test('plant list opens with every plant even when the box shows the chosen one, and leaving keeps the choice', () => {
  const page=makePage(async()=>({ok:true,json:async()=>({points:[],rows:[],counts:{}})}));
  vm.runInContext(plants,page.context);
  const box=page.element('plantSearch'), list=page.element('plantOptions');
  list.hidden=true;
  fire(box,'focus');
  assert.equal(list.hidden,false);
  assert.deepEqual(list.children.map(li=>li.textContent),['First plant (P1)','Second plant (P2)','Third (P3)']);
  assert.ok(list.children[0].classList.contains('chosen'));
  box.value='sec'; fire(box,'input');
  assert.deepEqual(list.children.map(li=>li.textContent),['Second plant (P2)']);
  assert.equal(page.element('plant').value,'P1');  // typing filters but does not choose
  fire(box,'blur');
  assert.equal(list.hidden,true);
  assert.equal(box.value,'First plant (P1)');
});

test('arrow keys and Enter choose a plant, and Escape closes the list without choosing', async () => {
  const requests=[];
  const page=makePage(async url=>{requests.push(url);return {ok:true,json:async()=>({points:[],rows:[],counts:{}})}});
  vm.runInContext(plants,page.context);
  const box=page.element('plantSearch'), list=page.element('plantOptions');
  fire(box,'focus');
  box.value='plant'; fire(box,'input');
  fire(box,'keydown',{key:'Escape'});
  assert.equal(list.hidden,true);
  assert.equal(box.value,'First plant (P1)');
  fire(box,'focus');
  fire(box,'keydown',{key:'ArrowDown'}); fire(box,'keydown',{key:'ArrowDown'});
  fire(box,'keydown',{key:'Enter'});
  assert.equal(list.hidden,true);
  assert.equal(page.element('plant').value,'P2');
  assert.equal(box.value,'Second plant (P2)');
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.ok(requests.some(url=>url.startsWith('/api/points')));
});

test('Enter on a typed search chooses the first match', async () => {
  const requests=[];
  const page=makePage(async url=>{requests.push(url);return {ok:true,json:async()=>({points:[],rows:[],counts:{}})}});
  vm.runInContext(plants,page.context);
  const box=page.element('plantSearch');
  fire(box,'focus');
  box.value='third'; fire(box,'input');
  fire(box,'keydown',{key:'Enter'});
  assert.equal(page.element('plant').value,'P3');
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.ok(requests.some(url=>url.startsWith('/api/readings')));
});

test('clicking a plant in the list chooses it', () => {
  const page=makePage(async()=>({ok:true,json:async()=>({points:[],rows:[],counts:{}})}));
  vm.runInContext(plants,page.context);
  fire(page.element('plantSearch'),'focus');
  page.element('plantOptions').children[2].onmousedown({preventDefault(){}});
  assert.equal(page.element('plant').value,'P3');
  assert.equal(page.element('plantOptions').hidden,true);
});
