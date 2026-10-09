// usage: node extract_data.cjs <pc-sheet artifact html> <out.json>
// Pulls the fan / cooler catalogs, fan noise and the 2026-10-07 in-stock prices out of the PC構成シート artifact,
// so the ranking uses exactly the same numbers and the same cooler-capacity estimate as the sheet.
const fs=require('fs'),vm=require('vm');
const s=fs.readFileSync(process.argv[2],'utf8');
const cut=(a,b)=>{const i=s.indexOf(a);if(i<0)throw Error('not found: '+a);const j=s.indexOf(b,i);if(j<0)throw Error('not found: '+b);return s.slice(i,j);};
const line=a=>{const i=s.indexOf(a);if(i<0)throw Error('not found: '+a);return s.slice(i,s.indexOf('\n',i));};
const code=[
  cut('const FAN_DB=','const MMH2O'),
  cut('const COOLER_BRANDS=','if(typeof module'),
  line('const FAN_NOISE='),line('const NOISE_SRC='),line('const PRICE_RESEARCH='),line('const PRICE_AS_OF='),
  'out={FAN_DB,COOLERS,FAN_NOISE,NOISE_SRC,PRICE_RESEARCH,cap:Object.fromEntries(COOLERS.map(c=>[c.id,coolerCapacity(c)]))};'
].join('\n');
const ctx={out:null};vm.createContext(ctx);vm.runInContext(code,ctx);
const o=ctx.out;
const fans=o.FAN_DB.filter(f=>!f.typ&&!f.aio).map(f=>({id:f.id,name:f.name,size:f.size,rpm:f.rpm,cfm:f.cfm,mm:f.mm,t:f.t||25,rev:!!f.rev,bundled:!!f.bundled,noRetail:f.noRetail||null,src:f.src||null}));
const aioFans=Object.fromEntries(o.FAN_DB.filter(f=>f.aio||f.id==='rx120'||f.id==='rs120'||f.id==='nfa12x25g2'||f.id==='p12pro'||f.id==='p14pro'||f.id==='nzf120p'||f.id==='nzf140p').map(f=>[f.id,{name:f.name,cfm:f.cfm,mm:f.mm,rpm:f.rpm}]));
for(const f of o.FAN_DB)aioFans[f.id]=aioFans[f.id]||{name:f.name,cfm:f.cfm,mm:f.mm,rpm:f.rpm};
const coolers=o.COOLERS.filter(c=>!c.typ).map(c=>Object.assign({},c,{cap:o.cap[c.id]}));
const P=o.PRICE_RESEARCH;
const res={fans,coolers,fanSpec:aioFans,noise:o.FAN_NOISE,noiseSrc:o.NOISE_SRC,price:{fan:P.fan||{},cooler:P.cooler||{}},priceDate:'2026-10-07'};
fs.writeFileSync(process.argv[3],JSON.stringify(res));
console.log('fans',fans.length,'coolers',coolers.length,'fanPrices',Object.keys(res.price.fan).length,'coolerPrices',Object.keys(res.price.cooler).length, 'keys',Object.keys(P));
