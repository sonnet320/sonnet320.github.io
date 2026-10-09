/* PC構成シート website integration. Same-origin, parent-only message protocol v1. */
let websiteComputing=false, websiteOffscreen=false, websiteHeightTimer=0;
function websitePicture(){
  draw();const image=document.createElement('canvas');const k=Math.min(1,1200/cv.width);
  image.width=Math.round(cv.width*k);image.height=Math.round(cv.height*k);const ctx=image.getContext('2d');
  ctx.fillStyle='#F7F9FB';ctx.fillRect(0,0,image.width,image.height);ctx.drawImage(cv,0,0,image.width,image.height);
  return image.toDataURL('image/jpeg',0.85);
}
function websiteSend(type,payload={},requestId){
  if(window.parent!==window)window.parent.postMessage({channel:'pc-sheet',version:1,type,...payload,requestId},location.origin);
}
function websiteHeight(){
  clearTimeout(websiteHeightTimer);
  websiteHeightTimer=setTimeout(()=>{
    const wrap=document.querySelector('.wrap');
    const bottom=wrap?wrap.getBoundingClientRect().bottom+window.scrollY:document.body.scrollHeight;
    websiteSend('height',{height:Math.ceil(bottom+parseFloat(getComputedStyle(document.body).paddingBottom||0)+8)});
  },100);
}
function websiteImport(data){
  if(websiteComputing)throw new Error('計算中です。少し待ってから読み込んでください。');
  const cfg=data&&data.state?data.state:data;
  if(!cfg||!Array.isArray(cfg.specs)||cfg.specs.length>100||!Array.isArray(cfg.fans)||cfg.fans.length>100)throw new Error('構成データの形式が違います。');
  if(JSON.stringify(cfg).length>500000)throw new Error('構成データが大きすぎます。');
  if(dim3){Air3D.stop();dim3=false;}
  loadSaved(JSON.stringify({...cfg,view:{...cfg.view,dim:'2d'}}));
  state.view.dim='2d';syncDim();save();warm=70;
  msg('構成を読み込みました。ファン配置や負荷を変更して確認できます。');
  websiteHeight();
  return {title:state.title};
}
function websiteResult(image=true){
  if(needRebuild)rebuild();
  const r=meas2d(), evaluation=diagEval(r.m,r.fq,r.coolQ,r.gpuQ,false);
  draw();
  return {schemaVersion:1,modelVersion:DIAG_VER,mode:'2d',computedAt:new Date().toISOString(),
    simulatedSeconds:Sim.time,settled:false,state:JSON.parse(JSON.stringify(state)),evaluation,
    conditions:{room:state.room,cpuMode:state.cpuMode,cpuLoad:state.cpuLoad,gpuLoad:state.gpuLoad,fanRpm:state.fanRpm,cpuPower:P.cpu,gpuPower:P.gpu},
    image:image?websitePicture():null};
}
async function websiteCompute(options={}){
  if(websiteComputing)throw new Error('計算中です。');
  if(dim3)await setDim('2d');
  websiteComputing=true;
  const prevRun=running,prevDiag=diagRun;
  const previousInert=document.body.inert;document.body.inert=true;
  running=false;diagRun=true;diagAbort=false;
  try{
    if(needRebuild)rebuild();
    const settle=clamp(+options.settle||6,2,30),avg=clamp(+options.avg||2,1,5);
    const r=await diag2d({settle,avg});
    if(!r)throw new Error('計算を中断しました。');
    const evaluation=diagEval(r.m,r.fq,r.coolQ,r.gpuQ,false);
    updateMetrics();draw();
    return {...websiteResult(false),evaluation,settled:true,simulatedSeconds:settle+avg,
      image:websitePicture(),calculation:{settle,average:avg,gridMm:Sim.HMM}};
  }finally{websiteComputing=false;diagRun=prevDiag;running=prevRun;warm=0;document.body.inert=previousInert;}
}

/* ---- daily prices (GPT's research → data/sheet-prices.json, made by tools/build/link_prices.py) ----
   the site's sheet replaces its built-in reference prices with the latest lowest in-stock price of each matched product */
let websiteLivePrices=null;
const websiteMd=d=>{const m=/^\d{4}-(\d{2})-(\d{2})$/.exec(d||'');return m?`${+m[1]}月${+m[2]}日`:d;};
async function websiteLoadLivePrices(){
  try{
    const r=await fetch('../data/sheet-prices.json',{cache:'no-cache'});if(!r.ok)return;
    const d=await r.json();if(!d||typeof d!=='object')return;
    const num=o=>Object.fromEntries(Object.entries(o||{}).filter(([k,v])=>typeof k==='string'&&Number.isFinite(v)&&v>0&&v<10000000));
    Object.assign(CPU_PRICE,num(d.cpu));Object.assign(GPU_CARD_PRICE,num(d.gpuCard));Object.assign(COOLER_PRICE,num(d.cooler));
    Object.assign(FAN_PRICE,num(d.fan));Object.assign(CASE_PRICE,num(d.case));
    websiteLivePrices=d;
    const days=[...new Set(Object.values(d.date||{}))].sort(), LBL={cpu:'CPU',gpuCard:'グラフィックボード',cooler:'CPUクーラー',fan:'ケースファン',case:'ケース'}, has=Object.keys(LBL).filter(k=>Object.keys(num(d[k])).length), n=has.reduce((s,k)=>s+Object.keys(num(d[k])).length,0);
    const card=document.getElementById('pricecard'), hint=card&&card.querySelector('.hint');
    if(hint&&n&&!document.getElementById('live-price-note')){
      const p=document.createElement('p');p.className='hint';p.id='live-price-note';
      p.textContent=`このサイトでは、毎日の価格調査(${days.length>1?websiteMd(days[0])+'〜'+websiteMd(days[days.length-1]):websiteMd(days[0])})で在庫ありの最安値が分かった${n}製品(${has.map(k=>LBL[k]).join('・')})の目安を、その価格に置き換えています。`;
      hint.after(p);
    }
    updatePrices();
  }catch(e){}
}

/* ---- parts from the price sheet (?parts=id,id,id or an 'apply-parts' message) ---- */
let websitePrices=null;
async function websitePriceData(){
  if(websitePrices)return websitePrices;
  const r=await fetch('../data/prices.json',{cache:'no-cache'});
  if(!r.ok)throw new Error('価格データを読み込めませんでした。');
  websitePrices=await r.json();return websitePrices;
}
function websiteGpuName(g){return /^RTX/i.test(g)?'GeForce '+g:/^RX/i.test(g)?'Radeon '+g:/^Arc/i.test(g)?'Intel '+g:g;}
async function websiteApplyParts(input){
  const list=(Array.isArray(input)?input:[]).map(x=>typeof x==='string'?x:x&&x.id);
  if(!list.length||list.length>12||list.some(id=>!/^[a-z0-9][a-z0-9-]{0,99}$/.test(id||'')))throw new Error('部品の指定が正しくありません。');
  if(websiteComputing)throw new Error('計算中です。少し待ってから読み込んでください。');
  const data=await websitePriceData(), day=data.updated, parts=[];
  for(const id of list){
    const prod=data.products.find(p=>p.id===id);if(!prod)throw new Error('部品が見つかりません: '+id);
    const offers=data.observations.filter(o=>o.id===id&&o.date===day&&o.status==='購入可'&&o.price).sort((a,b)=>a.price-b.price);
    parts.push({category:prod.category,id,name:prod.category==='GPU'?websiteGpuName(prod.group):prod.name,detail:prod.category==='SSD'?(prod.model||''):'',price:offers.length?offers[0].price:null});
  }
  if(dim3){Air3D.stop();dim3=false;}
  const r=applyPartsData({type:'pc-sheet-parts',version:1,date:day,parts});
  if(!r)throw new Error('構成表に入れられる部品がありませんでした。');
  state.view.dim='2d';syncDim();save();warm=70;
  msg(`価格シートで選んだ${r.done.join('・')}を構成表に入れました。`+(r.noPrice.length?`${r.noPrice.join('、')}は購入できる在庫がないため目安の価格です。`:''));
  websiteHeight();
  return {title:state.title,applied:r.done,noPrice:r.noPrice,total:parts.reduce((s,x)=>s+(x.price||0),0)};
}

/* ---- fans from the fan ranking (?fans=model:pos:count[:dir],… or an 'apply-fans' message) ---- */
function websiteApplyFans(input){
  const list=(Array.isArray(input)?input:[]).map(x=>{
    if(typeof x!=='string')return x;
    const [model,pos,count,dir]=x.split(':');return {model,pos,count:+count,dir};
  });
  if(!list.length||list.length>8||list.some(x=>!x||!/^[a-z0-9]{1,40}$/.test(x.model||'')))throw new Error('ファンの指定が正しくありません。');
  if(websiteComputing)throw new Error('計算中です。少し待ってから読み込んでください。');
  const r=applyFansData({type:'pc-sheet-fans',version:1,fans:list});
  if(!r)throw new Error('配置できるファンがありませんでした。');
  msg(fansImportText(r));websiteHeight();
  return {title:state.title,applied:r.done};
}
async function initWebsiteBridge(){
  document.documentElement.dataset.theme='light';
  window.PCSheet={version:1,importConfig:websiteImport,exportResult:websiteResult,computeResult:websiteCompute,
    getConfig:()=>JSON.parse(JSON.stringify(state)),applyParts:websiteApplyParts,applyFans:websiteApplyFans,
    createSample:(cpu,gpu,aio=false)=>{
      const cfg=sample();cfg.specs.find(r=>r.label==='CPU').name=cpu;cfg.specs.find(r=>r.label==='GPU').name=gpu;
      cfg.view={...cfg.view,dim:'2d',count:1000,arrows:true};
      if(aio){cfg.coolerBrand='Corsair';cfg.coolerModel='co-naut240';cfg.radSize=240;cfg.radPos='top';cfg.specs.find(r=>r.label==='クーラー').name='Corsair NAUTILUS 240 RS';}
      return cfg;
    }};
  const exp=document.getElementById('export-result');
  if(exp)exp.onclick=async()=>{
    exp.disabled=true;msg('2Dで安定するまで計算して、結果を書き出しています…');
    try{
      const data=await websiteCompute();
      const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
      a.href=url;a.download='pc-sheet-result.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      websiteSend('result',{result:data});msg('計算結果と図を書き出しました。');
    }catch(e){msg(e.message||'書き出しに失敗しました。');}finally{exp.disabled=false;}
  };
  window.addEventListener('message',async e=>{
    const d=e.data;
    if(e.source!==window.parent||e.origin!==location.origin||!d||d.channel!=='pc-sheet'||d.version!==1)return;
    try{
      if(d.type==='load-config')websiteSend('loaded',websiteImport(d.config),d.requestId);
      if(d.type==='apply-fans')websiteSend('loaded',websiteApplyFans(d.fans),d.requestId);
      if(d.type==='apply-parts')websiteSend('loaded',await websiteApplyParts(d.parts),d.requestId);
      if(d.type==='request-height')websiteHeight();
      if(d.type==='visibility')websiteOffscreen=d.visible===false;
      if(d.type==='export-result')websiteSend('result',{result:await websiteCompute()},d.requestId);
    }catch(e){websiteSend('error',{message:e.message||'読み込みに失敗しました。'},d.requestId);}
  });
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(websiteHeight).observe(document.querySelector('.wrap'));
  window.addEventListener('resize',websiteHeight);
  document.fonts?.ready.then(websiteHeight);
  const preset=new URLSearchParams(location.search).get('preset');
  if(preset){
    try{
      if(!/^[a-zA-Z0-9_-]{1,64}$/.test(preset))throw new Error('構成名が正しくありません。');
      const response=await fetch('../presets/'+preset+'.json');if(!response.ok)throw new Error('指定の構成が見つかりませんでした。');
      websiteImport(await response.json());
    }catch(e){msg(e.message);websiteSend('error',{message:e.message});}
  }
  const parts=new URLSearchParams(location.search).get('parts');
  if(parts){
    try{await websiteApplyParts(parts.split(',').filter(Boolean));}
    catch(e){msg(e.message);websiteSend('error',{message:e.message});}
  }
  const fans=new URLSearchParams(location.search).get('fans');
  if(fans){
    try{websiteApplyFans(fans.split(',').filter(Boolean));}
    catch(e){msg(e.message);websiteSend('error',{message:e.message});}
  }
  await websiteLoadLivePrices();
  websiteSend('ready');websiteHeight();
}
