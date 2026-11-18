// Read/render/recalculate only. Native XLSX export is unavailable in this runtime.
import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook} from '@oai/artifact-tool';
const input=process.argv[2], snapshots=JSON.parse(await fs.readFile(input,'utf8'));
const wb=Workbook.create();
for(const sheet of snapshots){
 const ws=wb.worksheets.add(sheet.name);ws.showGridLines=false;
 ws.getRange('A1').write(sheet.values);
 ws.getUsedRange().format.font={name:'Arial',size:11};
 ws.getUsedRange().format.rowHeight=23;
 for(const [address,formula] of sheet.formulas)ws.getRange(address).formulas=[[formula]];
 if(sheet.name==='OI Data'){
  ws.getRange('A1:K1').format={fill:'#224b77',font:{bold:true,color:'#ffffff'}};
  ws.getRange('A1:B13').format.columnWidth=21;ws.getRange('C1:C13').format.columnWidth=25;
  ws.getRange('D1:K13').format.columnWidth=21;
  ws.getRange('C2:C13').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  ws.getRange('H2:I13').setNumberFormat('#,##0.00');ws.getRange('K2:K13').setNumberFormat('#,##0.00');
 }else{
  ws.getRange('B2').format.font={size:16,bold:true};
  ws.getRange('B6:E6').format={fill:'#224b77',font:{bold:true,color:'#ffffff'},horizontalAlignment:'center'};
  ws.getRange('B6:B10').format.columnWidth=24;ws.getRange('C6:E10').format.columnWidth=20;
  ws.getRange('C7:E10').setNumberFormat('#,##0.00');ws.getRange('B10:E10').format.font={bold:true};
 }
}
wb.recalculate();
const checks=await wb.inspect({kind:'table',range:'OI Pivot!B6:E10',include:'values,formulas',tableMaxRows:5,tableMaxCols:4,maxChars:1600});
console.log(checks.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:20},maxChars:1000});
console.log(errors.ndjson);
for(const [sheet,range,file] of [['OI Pivot','B2:F11','pivot-preview.png'],['OI Data','A1:K13','data-preview.png']]){
 const image=await wb.render({sheetName:sheet,range,scale:1.5,format:'png'});
 await fs.writeFile(path.join(path.dirname(input),file),new Uint8Array(await image.arrayBuffer()));
}
await fs.writeFile(path.join(path.dirname(input),'artifact-read-check.json'),JSON.stringify({completed:true,checks:checks.records,errors:errors.records},null,2));
process.exit(0);
