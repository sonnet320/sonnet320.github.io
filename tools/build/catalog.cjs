// usage: node catalog.cjs <src/pc-sheet.html> <out.json>
// PC構成シートから、価格を結び付けるための製品の一覧を取り出す(CPU名・グラボのカードID・クーラー・ファン・ケース)。
const fs=require('fs'),vm=require('vm');
const s=fs.readFileSync(process.argv[2],'utf8');
const cut=(a,b)=>{const i=s.indexOf(a);if(i<0)throw Error('not found: '+a);const j=s.indexOf(b,i);if(j<0)throw Error('not found: '+b);return s.slice(i,j);};
const line=a=>{const i=s.indexOf(a);if(i<0)throw Error('not found: '+a);return s.slice(i,s.indexOf('\n',i));};
const code=[
  cut('const FAN_DB=','const MMH2O'),
  cut('const GPU_CHIPS=',"if(typeof module!=='undefined')module.exports={GPU_CHIPS"),
  line('const CASE_WORDS='),
  cut('const CPU_PRICE=','const COOLER_PRICE='),
  'out={cpu:Object.keys(CPU_PRICE),gpuCards:GPU_CARDS.map(c=>({id:c.id,brand:c.brand,series:c.series,chip:c.chip})),'
  +'coolers:COOLERS.filter(c=>c.brand).map(c=>({id:c.id,brand:c.brand,name:c.name,alias:c.alias||null})),'
  +'fans:FAN_DB.filter(f=>!f.typ).map(f=>({id:f.id,name:f.name,size:f.size})),'
  +'cases:CASE_WORDS.map(([re,k])=>[re.source,re.flags,k])};'
].join('\n');
const ctx={out:null};vm.createContext(ctx);vm.runInContext(code,ctx);
fs.writeFileSync(process.argv[3],JSON.stringify(ctx.out));
