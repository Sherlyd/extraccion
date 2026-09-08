// extract.js
// Extrae datos de una app de Qlik armando un hypercube (dimensiones +
// medidas) y los guarda en CSV y en Excel (.xlsx), pagina por pagina --
// con historiales de millones de filas (desde 2015), acumular todo en
// un array antes de guardar agota la memoria de Node. Esto escribe
// cada pagina apenas llega y la descarta, sin retenerla.
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
    filtroDocumento: 'Factura',
    dimensions: ['fv0_tipcmp', 'ClaveFecha', 'fv0_tipfor', 'sucurs', 'fv0_numero', 'client',
                 'Razon Social Distr', 'clv_client', 'Razon Social CF', 'fv1_itemcp', 'articu',
                 'Familia1', 'Familia2', 'Familia3', 'Familia4', 'Ejecutivo de Cuenta',
                 'Centro Distribucion', 'Zona Desc Distr', '_Documento'],
    measures: [
      { label: 'Cantid', expr: "Sum({1<_Documento={'Factura'}>} cantid)" },
      { label: 'Importe', expr: "Sum({1<_Documento={'Factura'}>} #Facturacion)" },
    ],
    outputFile: 'facturacion_detalle.csv',
  },
  {
    name: 'pedidos',
    filtroDocumento: 'Pedido',
    dimensions: ['numero', 'Tipo Pedido', 'client', 'Razon Social Distr', 'clv_client',
                 'Razon Social CF', 'pe1_itempe', 'articu', 'Familia1', 'Ejecutivo de Cuenta',
                 'sucurs', 'Centro Distribucion', 'Zona Desc Distr', '_Documento'],
    measures: [
      { label: 'Cantid', expr: "Sum({1<_Documento={'Pedido'}>} cantid)" },
      { label: 'Importe', expr: "Sum({1<_Documento={'Pedido'}>} #Pedidos)" },
    ],
    outputFile: 'pedidos_detalle.csv',
  },
  {
    name: 'cartera',
    dimensions: ['MesAño', 'pe1_numero', 'estado', 'Razon Social Distr', 'Razon Social CF',
                 'cls_sucurs', 'Ejecutivo de Cuenta', 'Vendedor', 'ONF Activa', 'Venc. ONF',
                 'Familia1', 'Centro Distribucion', 'Zona Desc Distr'],
    measures: [
      { label: 'Total Pendiente', expr: "Sum({1<Año,Mes,ClaveFecha,[Estado Pedido] -= {3,5,4,'D'},[A Fabricar] = {'S'}>} #Pedidos)" },
    ],
    outputFile: 'cartera_pendiente.csv',
  },
];

function celdaAValor(cell, esDimension) {
  if (!cell) return '';
  if (esDimension) {
    return cell.qText !== undefined ? cell.qText : cell.qNum;
  }
  return (cell.qNum !== undefined && cell.qNum !== 'NaN') ? cell.qNum : cell.qText;
}

// Extrae UNA definicion completa: abre el hypercube, y va escribiendo
// cada pagina a CSV y Excel apenas llega, sin acumular nada en memoria.
async function extraerYGuardar(app, def) {
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
  const numDimensions = dimHeaders.length;

  console.log(`  "${def.name}": columnas reales devueltas por Qlik (en orden): ${headers.join(' | ')}`);
  console.log(`  "${def.name}": ${totalRows} filas a traer... (${totalCols} columnas reales)`);

  const outDir = path.resolve(__dirname, config.outputPath);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const csvHeaders = headers.map((h) => ({ id: h, title: h }));
  const csvWriter = createObjectCsvWriter({
    path: path.join(outDir, def.outputFile),
    header: csvHeaders,
  });

  const xlsxFile = def.outputFile.replace(/\.csv$/i, '.xlsx');
  const workbookWriter = new ExcelJS.stream.xlsx.WorkbookWriter({
    filename: path.join(outDir, xlsxFile), useStyles: true,
  });
  const sheet = workbookWriter.addWorksheet(def.name.slice(0, 31));
  sheet.columns = headers.map((h) => ({ header: h, key: h, width: Math.max(12, h.length + 2) }));
  sheet.getRow(1).font = { bold: true };

  const MAX_CELLS_PER_REQUEST = 9000;
  const pageSize = Math.max(1, Math.floor(MAX_CELLS_PER_REQUEST / totalCols));

  let filasEscritas = 0;
  for (let top = 0; top < totalRows; top += pageSize) {
    const height = Math.min(pageSize, totalRows - top);

    let pagina;
    let ultimoError;
    for (let intento = 1; intento <= 3; intento++) {
      try {
        pagina = await obj.getHyperCubeData('/qHyperCubeDef', [
          { qTop: top, qLeft: 0, qHeight: height, qWidth: totalCols },
        ]);
        ultimoError = null;
        break;
      } catch (err) {
        ultimoError = err;
        console.warn(`    Pagina en fila ${top}: intento ${intento} fallo (${err.message}), reintentando...`);
        await new Promise((r) => setTimeout(r, 1500 * intento));
      }
    }
    if (ultimoError) throw ultimoError;

    const records = pagina[0].qMatrix.map((row) => {
      const record = {};
      headers.forEach((h, i) => { record[h] = celdaAValor(row[i], i < numDimensions); });
      return record;
    });

    await csvWriter.writeRecords(records);
    records.forEach((record) => sheet.addRow(record).commit());

    filasEscritas += records.length;
    if (totalRows > 50000 && top % 200000 < pageSize) {
      console.log(`    ... ${filasEscritas} / ${totalRows} filas`);
    }
  }

  sheet.commit();
  await workbookWriter.commit();

  console.log(`  Guardado en: output/${def.outputFile} y output/${xlsxFile} (${filasEscritas} filas)`);
}

// Corre UNA extraccion completa con conexion propia, reconectando desde
// cero si falla a mitad de camino (ej: "Request aborted").
async function extraerConReintentos(def, intentosMax = 3) {
  for (let intento = 1; intento <= intentosMax; intento++) {
    let session;
    try {
      const conectado = await openApp(config.appId);
      session = conectado.session;
      const app = conectado.app;

      await app.clearAll();

      if (def.filtroDocumento) {
        const campoDocumento = await app.getField('_Documento');
        await campoDocumento.selectValues([{ qText: def.filtroDocumento }], false, true);
      }

      await extraerYGuardar(app, def);

      if (def.filtroDocumento) {
        await app.clearAll();
      }

      await session.close();
      return;
    } catch (err) {
      console.warn(`  "${def.name}": intento ${intento}/${intentosMax} fallo (${err.message}).`);
      if (session) {
        try { await session.close(); } catch (e) { /* ya estaba caida */ }
      }
      if (intento === intentosMax) throw err;
      await new Promise((r) => setTimeout(r, 3000 * intento));
    }
  }
}

async function main() {
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js.');
    process.exit(1);
  }

  console.log('Iniciando extracciones:\n');

  for (const def of extractions) {
    console.log(`--- Procesando "${def.name}" ---`);
    await extraerConReintentos(def);
  }

  console.log('\nListo.');
}

main().catch((err) => {
  console.error('Error durante la extraccion (ya se agotaron los reintentos):', err.message || err);
  process.exit(1);
});