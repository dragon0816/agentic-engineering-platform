// The fixture adapter adds native PivotTable parts after this documented export.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [input, output, sourceUrl] = process.argv.slice(2);
const records = JSON.parse(await fs.readFile(input,'utf8'));
const wb=Workbook.create();
const pivot=wb.worksheets.add('OI Pivot');
const data=wb.worksheets.add('OI Data');
const headers=['OI Document','Line','CreatedAt','Sales','Customer','Status','Currency','OI Amount','FX to TWD','Month','OI TWD'];
const sales=[...new Set(records.map(r=>r.sales))].sort();
const months=[...new Set(records.map(r=>r.month))].sort();
// Explicit Excel serial preserves local wall-clock time. This runtime altered
// a Date at 16:00 UTC into next-day midnight; the independent oracle caught it.
const matrix=[headers,...records.map(r=>[r.document,r.line,Date.parse(r.created_at.replace(' ','T')+'Z')/86400000+25569,r.sales,r.customer,r.status,r.currency,r.amount,r.fx,r.month,null])];
data.getRange(`A1:K${matrix.length}`).values=matrix;
data.getRange('K2').formulas=[['=H2*I2']];data.getRange(`K2:K${matrix.length}`).fillDown();
data.getRange(`C2:C${matrix.length}`).setNumberFormat('yyyy-mm-dd hh:mm:ss');
data.getRange(`H2:I${matrix.length}`).setNumberFormat('#,##0.00');
data.getRange(`K2:K${matrix.length}`).setNumberFormat('#,##0.00');
data.tables.add(`A1:K${matrix.length}`,true,'OIData');
data.getRange(`A${matrix.length+3}`).values=[[`Source: ${sourceUrl} — fictional records. CreatedAt is Asia/Taipei local time.`]];
data.getRange(`A${matrix.length+4}`).values=[['Test FX: USD to TWD 32; TWD to TWD 1. No live exchange rates.']];
data.freezePanes.freezeRows(1);
const totals=sales.map(s=>months.map(m=>records.filter(r=>r.sales===s&&r.month===m).reduce((v,r)=>v+Math.round(r.amount*r.fx*100),0)/100));
const result=[['Sales',...months,'Grand Total'],...sales.map((s,i)=>[s,...totals[i],totals[i].reduce((a,b)=>a+b,0)])];
const columnTotals=months.map((m,i)=>totals.reduce((a,r)=>a+r[i],0));
result.push(['Grand Total',...columnTotals,columnTotals.reduce((a,b)=>a+b,0)]);
pivot.getRange('B2').values=[['OI by Sales and Month (TWD)']];
pivot.getRange('B3').values=[['2026-09-01 to 2026-10-31 inclusive, Asia/Taipei']];
pivot.getRange('B4').values=[['Booked OI lines, including signed adjustments and zero amounts']];
pivot.getRange('B6').write(result);
for(const sheet of [pivot,data]){sheet.showGridLines=false;sheet.getUsedRange().format.font={name:'Arial',size:11};sheet.getUsedRange().format.rowHeight=23;}
pivot.getRange('B2').format.font={size:16,bold:true};
pivot.getRange('B3:B4').format.font={size:10,color:'#526174'};
pivot.getRange('B6:E6').format={fill:'#224b77',font:{bold:true,color:'#ffffff'},horizontalAlignment:'center'};
pivot.getRange('B10:E10').format.font={bold:true};
pivot.getRange('C7:E10').setNumberFormat('#,##0.00');
pivot.getRange('B6:B10').format.columnWidth=23;pivot.getRange('C6:E10').format.columnWidth=20;
data.getRange('A1:K1').format={fill:'#224b77',font:{bold:true,color:'#ffffff'}};
data.getRange('A1:B13').format.columnWidth=16;data.getRange('C1:C13').format.columnWidth=23;
data.getRange('D1:F13').format.columnWidth=23;data.getRange('G1:K13').format.columnWidth=18;
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'OI Pivot!B6:E10',include:'values,formulas',tableMaxRows:6,tableMaxCols:5,maxChars:1600})).ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:20},maxChars:1000});
console.log(errors.ndjson);
await fs.mkdir(path.dirname(output),{recursive:true});
for(const [sheet,range,file] of [['OI Pivot','B2:F11','pivot-preview.png'],['OI Data','A1:K13','data-preview.png']]){
 const image=await wb.render({sheetName:sheet,range,scale:1.5,format:'png'});
 await fs.writeFile(path.join(path.dirname(output),file),new Uint8Array(await image.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(output);
// Every file operation above has completed. Explicit normal termination avoids
// a reproducible Windows native-runtime shutdown failure (0xC0000409). The Host
// still requires an independent saved-workbook oracle; exit 0 is not acceptance.
process.exit(0);
