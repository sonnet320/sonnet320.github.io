'use strict';
const $=id=>document.getElementById(id), frame=$('pc-sheet');
const tiers={20:'20万円以下',30:'30万円以下',40:'40万円以下',plus:'40万円以上'};
let config=null,selected=null,currentTier='all',sheetReady=false,resultSequence=0,loadingBuild=false;
const cache=new Map(),pending=new Map();
const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n;};
function safeURL(value){try{const u=new URL(value,location.href);return ['https:','http:'].includes(u.protocol)?u:null;}catch{return null;}}
function localURL(value){const u=safeURL(value);if(!u||u.origin!==location.origin)throw new Error('構成と計算結果は同じサイト内に置いてください。');return u.href;}
async function getJSON(path){const u=localURL(path);if(!cache.has(u))cache.set(u,fetch(u).then(r=>{if(!r.ok)throw new Error('ファイルが見つかりません。');return r.json();}).catch(e=>{cache.delete(u);throw e;}));return cache.get(u);}
function send(type,payload={}){frame.contentWindow.postMessage({channel:'pc-sheet',version:1,type,...payload},location.origin);}
function request(type,payload){return new Promise((resolve,reject)=>{const id=crypto.randomUUID?.()||String(Date.now());const timer=setTimeout(()=>{pending.delete(id);reject(new Error('シートへの読み込みが完了しませんでした。シートを開き直してください。'));},15000);pending.set(id,{resolve,reject,timer});send(type,{...payload,requestId:id});});}
window.addEventListener('message',e=>{
  const d=e.data;if(e.source!==frame.contentWindow||e.origin!==location.origin||!d||d.channel!=='pc-sheet'||d.version!==1)return;
  if(d.type==='ready'){sheetReady=true;$('sheet-status').textContent='変更内容はこのブラウザに保存';if(selected&&!loadingBuild)$('load-build').disabled=false;send('request-height');}
  if(d.type==='height'&&Number.isFinite(d.height)&&d.height>0){frame.dataset.contentHeight=String(Math.min(50000,d.height));resizeFrame();}
  if(d.requestId&&pending.has(d.requestId)){const p=pending.get(d.requestId);clearTimeout(p.timer);pending.delete(d.requestId);if(d.type==='error')p.reject(new Error(d.message));else p.resolve(d);}
  else if(d.type==='error'){$('sheet-status').textContent=d.message;}
});
const mobile=matchMedia('(max-width:899px)');
function resizeFrame(){frame.style.height=mobile.matches?(frame.dataset.contentHeight||1800)+'px':'';}
mobile.addEventListener('change',()=>{resizeFrame();send('request-height');});
frame.addEventListener('load',()=>send('request-height'));
if('IntersectionObserver'in window)new IntersectionObserver(entries=>{send('visibility',{visible:entries[0].isIntersecting});},{rootMargin:'200px'}).observe(frame);
function displayLink(id,url,label){const a=$(id),u=safeURL(url);a.hidden=!url||!u;if(u){a.href=u.href;if(label)a.textContent=label;}}
function tierOf(p){if(Number.isFinite(p.price)&&p.price>0)return p.price<=200000?'20':p.price<=300000?'30':p.price<=400000?'40':'plus';return String(p.tier);}
function renderCards(){
  const list=$('product-list');list.replaceChildren();
  const products=config.products.filter(p=>currentTier==='all'||tierOf(p)===currentTier);
  $('card-count').textContent=products.length+'件の構成'+(products.every(p=>p.sample)?' · 表示サンプル':'');
  for(const p of products){
    const b=node('button','product-card');b.type='button';b.dataset.id=p.id;b.setAttribute('aria-pressed',String(selected?.id===p.id));
    b.setAttribute('aria-label',p.name+'の計算結果を見る');
    const top=node('div','card-top');top.append(node('span','tier-badge tier-'+tierOf(p),tiers[tierOf(p)]||'価格未登録'),node('span','sample-label',p.sample?p.model:p.pr?'PR':''));b.append(top,node('h3','',p.name),node('p','card-shop',p.shop+(p.sample?'':' · '+p.model)));
    const dl=node('dl','card-specs');for(const [k,v]of [['CPU',p.cpu],['GPU',p.gpu],['RAM',p.memory],['SSD',p.ssd]])dl.append(node('dt','',k),node('dd','',v));b.append(dl);
    const bottom=node('div','card-bottom');bottom.append(node('span','price',p.price?'¥'+p.price.toLocaleString('ja-JP'):'価格未登録'),node('span','select-label',selected?.id===p.id?'選択中':'結果を見る'));b.append(bottom);
    if(p.price&&p.priceDate)b.append(node('p','price-date',p.priceDate+'時点・税込'));
    if(p.genericCase)b.append(node('p','generic-note','目安（汎用ケースで計算）'));
    b.addEventListener('click',()=>selectProduct(p));list.append(b);
  }
  if(!products.length)list.append(node('p','', 'この価格帯の商品はまだ掲載されていません。'));
}
function showTemp(id,value){const n=$(id);n.replaceChildren();if(Number.isFinite(value))n.append(document.createTextNode(value.toFixed(1)),node('small','','°C'));else n.textContent='—';}
async function selectProduct(p){
  selected=p;const seq=++resultSequence;renderCards();$('result-title').textContent=p.name;
  $('result-subtitle').textContent=p.cpu+' / '+p.gpu;
  $('result-error').hidden=true;$('result-image').hidden=true;$('result-placeholder').hidden=false;$('result-placeholder').textContent='計算結果を読み込み中';
  ['temp-cpu','temp-gpu','temp-vrm','result-grade'].forEach(id=>$(id).textContent='—');$('result-conditions').replaceChildren();
  $('load-build').disabled=!sheetReady||loadingBuild;$('load-status').textContent='';
  $('case-note').textContent=p.genericCase?'目安（汎用ケースで計算）':'ケース：'+p.case;
  const shop=safeURL(p.affiliateUrl);$('shop-link').hidden=!p.affiliateUrl||!shop||p.sample;if(shop)$('shop-link').href=shop.href;
  try{
    const r=await getJSON(p.result);if(seq!==resultSequence)return;
    if(r.presetId&&r.presetId!==p.id)throw new Error('この構成と計算結果が一致していません。');
    if(!r.evaluation)throw new Error('計算結果がまだ登録されていません。');
    const e=r.evaluation;showTemp('temp-cpu',e.cpu);showTemp('temp-gpu',e.gpu);showTemp('temp-vrm',e.vrm);
    $('result-grade').textContent=e.grade?(e.grade+' · '+e.score+'点'):'評価なし';
    const c=r.conditions||{};const dl=$('result-conditions');
    for(const [k,v]of [['室温',c.room+'°C'],['負荷','CPU '+c.cpuLoad+'% / GPU '+c.gpuLoad+'%'],['ファン回転数',c.fanRpm+'%'],['計算条件','2D · '+(r.calculation?.gridMm||5)+'mm格子 / '+r.simulatedSeconds+'秒'],['計算日',r.computedAt?.slice(0,10)||'未登録']])dl.append(node('dt','',k),node('dd','',v));
    const img=r.image;if(typeof img==='string'&&(/^data:image\/(png|jpeg);base64,/.test(img)||safeURL(img)?.origin===location.origin)){
      const image=$('result-image');image.onload=()=>{if(seq===resultSequence){image.hidden=false;$('result-placeholder').hidden=true;}};image.onerror=()=>{$('result-placeholder').textContent='図を読み込めませんでした。温度は上の計算条件による結果です。';};image.src=img;image.alt=p.name+'：2Dで計算した空気の流れと温度分布';
    }else $('result-placeholder').textContent='エアフロー図が未登録です。';
  }catch(e){if(seq!==resultSequence)return;$('result-placeholder').textContent='計算結果を表示できません';$('result-error').textContent=e.message+' 上のシートに読み込んで確認できます。';$('result-error').hidden=false;}
}
document.querySelectorAll('[data-tier]').forEach(b=>b.addEventListener('click',()=>{
  currentTier=b.dataset.tier;document.querySelectorAll('[data-tier]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));renderCards();
  const visible=config.products.filter(p=>currentTier==='all'||tierOf(p)===currentTier);if(visible.length&&!visible.some(p=>p.id===selected?.id))selectProduct(visible[0]);
}));
$('load-build').addEventListener('click',async()=>{
  if(!selected||!sheetReady||loadingBuild)return;loadingBuild=true;$('load-build').disabled=true;const p=selected;$('load-status').textContent='構成をシートに読み込んでいます…';
  try{const data=await getJSON(p.preset);await request('load-config',{config:data});$('load-status').textContent=p.name+'を読み込みました。';$('sheet').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});}
  catch(e){$('load-status').textContent=e.message;}finally{loadingBuild=false;$('load-build').disabled=!sheetReady;}
});
(async()=>{
  try{
    config=await getJSON('config.json');if(!Array.isArray(config.products))throw new Error('構成一覧の形式が違います。');
    $('site-name').textContent=config.siteName;$('footer-name').textContent=config.siteName;document.title=config.sheetName+' | '+config.siteName;
    $('menu').replaceChildren();for(const item of config.menu||[]){if(!/^#[a-zA-Z][\w-]*$/.test(item.href))continue;const a=node('a','',item.label);a.href=item.href;$('menu').append(a);}
    displayLink('channel-link',config.channelUrl);displayLink('contact-link',config.contactUrl);
    $('sample-notice').hidden=!config.products.some(p=>p.sample);renderCards();if(config.products.length)selectProduct(config.products[0]);
  }catch(e){$('card-count').textContent='一覧を読み込めませんでした';$('catalog-error').textContent=e.message+' 公開後のURL、またはローカルサーバーから開いてください。';$('catalog-error').hidden=false;}
})();
