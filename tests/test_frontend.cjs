// Fixture tests for UI logic; these do not replace a real browser test.
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const html = fs.readFileSync(path.join(__dirname,'../templates/dashboard.html'),'utf8');
const source = fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
assert.equal(ids.length,new Set(ids).size,'Duplicate template IDs');
const nodes = {};
function element() {return {value:'',textContent:'',innerHTML:'',hidden:false,disabled:false,style:{},dataset:{},children:[],classList:{add(){},remove(){},toggle(){}},addEventListener(){},replaceChildren(...children){this.children=children;this.innerHTML='';},add(child){this.children.push(child);}};}
for(const id of ids) nodes[id]=element();
nodes.confSlider.value='0.25'; nodes.imageSize.value='640'; nodes.voiceEnabled.value='on';
for (const match of source.matchAll(/\$\('([^']+)'\)/g)) {
  if (match[1]!=='view-') assert.ok(nodes[match[1]],`Missing template id ${match[1]}`);
}
const stats={total_images:0,signs_detected:0,safety_alerts:0,warning_signs:0,recent:[],breakdown:[]};
let fetchImpl=async url=>({ok:true,status:200,redirected:false,headers:{get:()=> 'application/json'},json:async()=>url.includes('model-info')?{names:{0:'STOP'},sign_info:{STOP:{label:'Stop'}},model:'best.pt',default_imgsz:640}:url.includes('history')?[]:stats});
const context=vm.createContext({console,URL,FormData,Map,Set,Option:function(text,value){this.text=text;this.value=value;},localStorage:{getItem:()=>null,setItem(){}},document:{getElementById:id=>{assert.ok(nodes[id],id);return nodes[id];},querySelectorAll:()=>[],createElement:()=>element()},window:{SIGN_INFO:{},addEventListener(){},scrollTo(){},location:{assign(){}}},fetch:(...args)=>fetchImpl(...args)});
vm.runInContext(source,context);
function run(code){return vm.runInContext(code,context);}
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));
 const info={label:'Speed limit 40 km/h',meaning:'A numeric limit sign',rule:'Verify the image',icon:'x'};
 context.fixture={detections:[{class:'SPEED_LIMIT_40',confidence:.9,info}],annotated_image:'data:image/png;base64,AA',elapsed_ms:20,model:'best_india.pt',imgsz:960};
 run('renderResults(fixture)');
 assert.equal(nodes.resultImgWrap.children.length,1,'Exactly one annotated image, no duplicate overlays');
 assert.match(nodes.signCardsList.innerHTML,/Speed limit 40/);
 assert.equal(nodes.voiceBtn.disabled,true,'Unavailable speech is disabled');
 const many=Array.from({length:85},(_,i)=>({class:'C'+i,label:'Category '+i,pct:1}));
 context.many=many;
 assert.equal((run('categoryRows(many)').match(/class="cat-bar"/g)||[]).length,85);
 context.fixture.detections[0].info.label='<img src=x onerror=alert(1)>';
 run('renderResults(fixture)');
 assert.ok(!nodes.signCardsList.innerHTML.includes('<img src=x'));
 assert.ok(nodes.signCardsList.innerHTML.includes('&lt;img'));
 run('historyEntries = [{class:"STOP",timestamp:"2026-09-17",confidence:.9,info:{label:"Stop"}},{class:"SPEED_LIMIT_40",timestamp:"2026-09-17",confidence:.8,info:{label:"Speed limit 40"}}]');
 nodes.historyClassFilter.value='SPEED_LIMIT_40'; run('renderHistory()');
 assert.ok(nodes.historyTimeline.innerHTML.includes('Speed limit 40'));
 assert.ok(!nodes.historyTimeline.innerHTML.includes('>Stop<'));
 fetchImpl=async()=>{throw new Error('Network unavailable');};
 context.file={};run('selectedFile = file');
 await run('runAnalysis()');
 assert.equal(nodes.analyzeBtn.disabled,false,'Failed request releases busy state');
 assert.match(nodes.appError.textContent,/Network unavailable/);
 console.log('PASS: template IDs, single annotated image, dynamic classes, 85-category chart, text escaping, history filter, voice fallback, failed-request recovery');
})().catch(error=>{console.error(error);process.exitCode=1;});
