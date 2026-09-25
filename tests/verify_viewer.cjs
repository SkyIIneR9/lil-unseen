// Exercise both real viewer templates with invented data and an inert DOM.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(){this.children=[];this.value='';this.checked=false;this.listeners={};this.textContent=''}
  append(...elements){this.children.push(...elements)}
  replaceChildren(...elements){this.children=elements}
  addEventListener(event,fn){this.listeners[event]=fn}
  setAttribute(name,value){this[name]=value}
  focus(){this.focused=true}
  select(){this.selected=true}
}
const root=path.join(__dirname,'..');
for(const template of ['viewer.html','viewer_en.html']){
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/report.json'),'utf8'));
  const elements={};
  for(const id of ['data','search','view','scope','file','mods','hideBonusOff','stats','counter','page','prev','next','results'])elements[id]=new Element();
  elements.data.textContent=JSON.stringify(data).replaceAll('<','\\u003c').replaceAll('>','\\u003e').replaceAll('&','\\u0026');
  elements.scope.value='partial';elements.hideBonusOff.checked=true;elements.view.value='fragments';
  const context={document:{getElementById:id=>elements[id],createElement:()=>new Element()},navigator:{},window:{scrollTo(){}},setTimeout:fn=>fn(),clearTimeout(){}};
  vm.createContext(context);
  const html=fs.readFileSync(path.join(root,'research_unseen',template),'utf8');
  vm.runInContext(html.match(/<script>\s*('use strict';[\s\S]*?)<\/script>/)[1],context);
  const groups=()=>vm.runInContext('filtered',context);
  const eligible=data.rows.filter(r=>!r.mod&&!r.bonus_off&&r.status==='partial');
  assert.equal(groups().length,new Set(eligible.map(r=>r.fragment_id)).size);
  elements.scope.value='all';elements.scope.listeners.change();
  assert.equal(groups().length,new Set(data.rows.filter(r=>!r.mod&&!r.bonus_off).map(r=>r.fragment_id)).size);
  elements.view.value='lines';elements.view.listeners.change();
  assert.equal(groups().length,data.rows.filter(r=>!r.mod&&!r.bonus_off).length);
  elements.hideBonusOff.checked=false;elements.hideBonusOff.listeners.change();
  elements.mods.checked=true;elements.mods.listeners.change();
  assert.equal(groups().length,data.rows.length);
  elements.next.onclick();assert.match(elements.page.textContent,/^2 /);
  elements.search.value='___no_such_line___';elements.search.listeners.input();
  assert.equal(elements.results.children.length,0);assert.equal(elements.next.disabled,true);
  elements.view.value='fragments';elements.view.listeners.change();
  elements.search.value=data.rows[2].id;elements.search.listeners.input();
  assert.equal(groups().length,1);assert.equal(groups()[0].rows.length,3);
  context.sample=data.rows[0];
  assert.equal(vm.runInContext('jumpCommand(sample)',context),`unseen_research_jump(${JSON.stringify(data.rows[0].id)})`);
  const exact=vm.runInContext('jumpCommand(sample,"line")',context);
  assert.ok(exact.indexOf('lookup(')<exact.indexOf('pop_call()'));
  const panel=vm.runInContext('jumpPanel(sample)',context),actions=panel.children[0],command=panel.children[1];
  actions.children[0].onclick();assert.equal(command.selected,true);assert.match(panel.children[2].textContent,/Ctrl\+C/);
  actions.children[2].onclick();assert.ok(!command.value.includes('default_translates'));
  assert.ok(!elements.data.textContent.includes('</script>'));
  console.log(`PASS ${template}: filters, mods, pagination, grouping, whole-fragment search, jump commands and clipboard fallback.`);
}
