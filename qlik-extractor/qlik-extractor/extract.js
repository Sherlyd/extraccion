// extract.js
// Extrae datos de una app de Qlik armando un hypercube (dimensiones +
// medidas) y los guarda en CSV y en Excel (.xlsx).
//
// Uso: npm run extract

const path = require('path');
const fs = require('fs');
const { createObjectCsvWriter } = require('csv-writer');
const ExcelJS = require('exceljs');
const config = require('./config');
const { openApp } = require('./qlik-session');


const extractions = [
  {
    name: 'facturacion',
    dimensions: ['fv0_tipcmp', 'fv0_fecalt', 'fv0_tipfor', 'sucurs', 'fv0_numero', 'client',
                 'Razon Social Distr', 'clv_client', 'Razon Social CF', 'fv1_itemcp', 'articu',
                 'Familia1', 'Ejecutivo de Cuenta', 'Centro Distribucion', 'Zona Desc Distr', '_Documento'],
    measures: [
      { label: 'Cantid', expr: 'Sum(cantid)' },
      { label: 'Importe', expr: 'Sum(#Facturacion)' },
    ],
    outputFile: 'facturacion_detalle.csv',
  },
  {
    name: 'pedidos',
    dimensions: ['numero', 'Tipo Pedido', 'client', 'Razon Social Distr', 'clv_client',
                 'Razon Social CF', 'pe1_itempe', 'articu', 'Familia1', 'Ejecutivo de Cuenta',
                 'sucurs', 'Centro Distribucion', 'Zona Desc Distr', '_Documento'],
    measures: [
      { label: 'Cantid', expr: 'Sum(cantid)' },
      { label: 'Importe', expr: 'Sum(#Pedidos)' },
    ],
    outputFile: 'pedidos_detalle.csv',
  },
  {
    name: 'cartera',
    dimensions: ['MesAño', 'pe1_numero', 'estado', 'Razon Social Distr', 'Razon Social CF',
                 'cls_sucurs', 'Ejecutivo de Cuenta', 'Vendedor', 'ONF Activa', 'Venc. ONF',
                 'Familia1', 'Centro Distribucion', 'Zona Desc Distr'],
    measures: [
      { label: 'Total Pendiente', expr: "Sum({<Año,Mes,ClaveFecha,[Estado Pedido] -= {3,5,4,'D'},[A Fabricar] = {'S'}>} #Pedidos)" },
    ],
    outputFile: 'cartera_pendiente.csv',
  },
];


async function extractOne(app, def) {
  const hypercubeDef = {
    qDimensions: def.dimensions.map((f) => ({ qDef: { qFieldDefs: [f] } })),
    qMeasures: def.measures.map((m) => ({ qDef: { qDef: m.expr, qLabel: m.label } })),
    qInitialDataFetch: [{ qTop: 0, qLeft: 0, qHeight: 0, qWidth: def.dimensions.length + def.measures.length }],
    qSuppressMissing: false,
    qSuppressZero: false,
  };

  const obj = await app.createSessionObject({
    qInfo: { qType: `extract-${def.name}` },
    qHyperCubeDef: hypercubeDef,
  });

  const layout = await obj.getLayout();
  const totalRows = layout.qHyperCube.qSize.qcy;

  const dimHeaders = layout.qHyperCube.qDimensionInfo.map((d) => d.qFallbackTitle);
  const measHeaders = layout.qHyperCube.qMeasureInfo.map((m) => m.qFallbackTitle);
  const headers = [...dimHeaders, ...measHeaders];
  const totalCols = headers.length;

  console.log(`  "${def.name}": columnas reales devueltas por Qlik (en orden): ${headers.join(' | ')}`);

  const pedidas = def.dimensions.length + def.measures.length;
  if (totalCols !== pedidas) {
    console.warn(`  AVISO: pediste ${pedidas} columnas pero Qlik devolvio ${totalCols}.`);
  }

  console.log(`  "${def.name}": ${totalRows} filas a traer... (${totalCols} columnas reales)`);

  const MAX_CELLS_PER_REQUEST = 9000;
  const pageSize = Math.max(1, Math.floor(MAX_CELLS_PER_REQUEST / totalCols));

  const allRows = [];
  for (let top = 0; top < totalRows; top += pageSize) {
    const height = Math.min(pageSize, totalRows - top);
    const pages = await obj.getHyperCubeData('/qHyperCubeDef', [
      { qTop: top, qLeft: 0, qHeight: height, qWidth: totalCols },
    ]);
    pages[0].qMatrix.forEach((row) => allRows.push(row));
  }

  return { rows: allRows, headers, numDimensions: dimHeaders.length };
}

function celdaAValor(cell, esDimension) {
  if (!cell) return '';
  if (esDimension) {
    return cell.qText !== undefined ? cell.qText : cell.qNum;
  }
  return (cell.qNum !== undefined && cell.qNum !== 'NaN') ? cell.qNum : cell.qText;
}

async function saveToCsv(def, headers, rows, numDimensions) {
  const outDir = path.resolve(__dirname, config.outputPath);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const csvHeaders = headers.map((h) => ({ id: h, title: h }));
  const csvWriter = createObjectCsvWriter({
    path: path.join(outDir, def.outputFile),
    header: csvHeaders,
  });

  const records = rows.map((row) => {
    const record = {};
    csvHeaders.forEach((h, i) => {
      record[h.id] = celdaAValor(row[i], i < numDimensions);
    });
    return record;
  });

  await csvWriter.writeRecords(records);
  console.log(`  Guardado en: output/${def.outputFile} (${records.length} filas)`);
}

async function saveToXlsx(def, headers, rows, numDimensions) {
  const outDir = path.resolve(__dirname, config.outputPath);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const xlsxFile = def.outputFile.replace(/\.csv$/i, '.xlsx');
  const filePath = path.join(outDir, xlsxFile);
  const workbookWriter = new ExcelJS.stream.xlsx.WorkbookWriter({ filename: filePath, useStyles: true });
  const sheet = workbookWriter.addWorksheet(def.name.slice(0, 31));

  sheet.columns = headers.map((h) => ({ header: h, key: h, width: Math.max(12, h.length + 2) }));
  sheet.getRow(1).font = { bold: true };

  rows.forEach((row) => {
    const record = {};
    headers.forEach((h, i) => {
      record[h] = celdaAValor(row[i], i < numDimensions);
    });
    sheet.addRow(record).commit();
  });

  sheet.commit();
  await workbookWriter.commit();
  console.log(`  Guardado en: output/${xlsxFile} (${rows.length} filas)`);
}

async function main() {
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js.');
    process.exit(1);
  }

  console.log('Conectando a la app...');
  const { session, app } = await openApp(config.appId);
  console.log('Conectado. Iniciando extracciones:\n');

  for (const def of extractions) {
    const { rows, headers, numDimensions } = await extractOne(app, def);
    await saveToCsv(def, headers, rows, numDimensions);
    await saveToXlsx(def, headers, rows, numDimensions);
  }

  await session.close();
  console.log('\nListo.');
}

main().catch((err) => {
  console.error('Error durante la extraccion:', err.message || err);
  process.exit(1);
});