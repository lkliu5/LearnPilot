const {chromium}=require('playwright');const path=require('path');
(async()=>{const files=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PW_CHROME_EXE});
const pg=await b.newPage({viewport:{width:960,height:540},deviceScaleFactor:2});
for(const f of files){await pg.goto('file://'+path.resolve('slides/'+f+'.html'));await pg.waitForTimeout(150);
await pg.screenshot({path:'shot_'+f+'.png'});console.log('shot',f);}
await b.close();})();
