// extract.js
// Extrae datos de una app de Qlik armando un hypercube (dimensiones +
// medidas) y los guarda en un CSV. Este es el script que despues
// automatizo (cron, Task Scheduler, etc.) para correr periodicamente.
//
// Uso: npm run extract

const path = require('path');
const fs = require('fs');
const { createObjectCsvWriter } = require('csv-writer');
const config = require('./config');
const { openApp } = require('./qlik-session');

// -----------------------------------------------------------------------
// DEFINIR ACA QUE SE DESEA EXTRAER.
// Cada entrada de "extractions" es un conjunto independiente de datos que
// se guarda en su propio CSV. Agrega tantas como se necesite.
//
// - dimensions: campos "de agrupacion" (texto, categorias, fechas, etc.)
// - measures: expresiones de calculo, en la misma sintaxis que usaria
//   dentro de una expresion de Qlik (Sum(), Count(), Avg(), etc.)
// - outputFile: nombre del CSV de salida dentro de config.outputPath
//
// Los nombres de campo exactos los saca corriendo antes: npm run list-fields
const extractions = [
  {
    name: 'facturacion',
    dimensions: ['Fecha de Alta', 'Tipo Comp', 'Distr.', 'Razon Social Distr', 'Razon Social CF',
                 'Artículo', 'Familia1', 'Ejecutivo de Cuenta', 'Suc.'],
    measures: [
      { label: 'Cantid', expr: 'Sum(cantid)' },
      // OJO: reemplazar por la expresion real de importe neto que usa
      // el sheet de Qlik (Edit sheet -> click en la medida -> copiar
      // la expresion exacta). No usar un Sum() simple sin confirmar.
      { label: 'Importe', expr: 'Sum(fv0_impnet)' },
    ],
    outputFile: 'facturacion_detalle.csv',
  },
  {
    name: 'pedidos',
    dimensions: ['numero', 'Razon Social Distr', 'ARTICULO', 'Familia1', 'Ejecutivo de Cuenta', 'Suc.'],
    measures: [
      // OJO: confirmar si el campo de cantidad pedida es pe1_candes,
      // pe1_canrem, u otro -- verificar contra el sheet real.
      { label: 'Cantid', expr: 'Sum(pe1_candes)' },
    ],
    outputFile: 'pedidos_detalle.csv',
  },
  {
    name: 'cartera',
    dimensions: ['MesAño', 'pe1_numero', 'estado', 'Razon Social Distr', 'Razon Social CF',
                 'cls_sucurs', 'Ejecutivo de Cuenta', 'Vendedor', 'ONF Activa', 'Venc. ONF'],
    measures: [
      // Confirmado: es la misma medida maestra "Total Pedidos Ptes." que
      // usa el propio cuadro "Detalle Colchon". OJO: esto es backlog de
      // produccion/entrega, NO cartera por cobrar. Nota: no divido por
      // 1000 aca (eso era solo formato de pantalla), guardamos el numero
      // completo en pesos.
      { label: 'Total Pendiente', expr: "Sum({<Año,Mes,ClaveFecha,[Estado Pedido] -= {3,5,4,'D'},[A Fabricar] = {'S'}>} #Pedidos)" },
    ],
    outputFile: 'cartera_pendiente.csv',
  },
];

const PAGE_SIZE = 5000;

async function extractOne(app, def) {
  const hypercubeDef = {
    qDimensions: def.dimensions.map((f) => ({ qDef: { qFieldDefs: [f] } })),
    qMeasures: def.measures.map((m) => ({ qDef: { qDef: m.expr, qLabel: m.label } })),
    qInitialDataFetch: [{ qTop: 0, qLeft: 0, qHeight: 0, qWidth: def.dimensions.length + def.measures.length }],
  };

  const obj = await app.createSessionObject({
    qInfo: { qType: `extract-${def.name}` },
    qHyperCubeDef: hypercubeDef,
  });

  const layout = await obj.getLayout();
  const totalRows = layout.qHyperCube.qSize.qcy;
  const totalCols = def.dimensions.length + def.measures.length;

  console.log(`  "${def.name}": ${totalRows} filas a traer...`);

  // El motor de Qlik limita cada pedido a 10.000 celdas (qHeight x qWidth).
  // Calculamos cuantas filas entran por pagina segun el ancho real de
  // esta extraccion, con margen de seguridad.
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

  return allRows;
}

async function saveToCsv(def, rows) {
  const outDir = path.resolve(__dirname, config.outputPath);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const headers = [
    ...def.dimensions.map((f) => ({ id: f, title: f })),
    ...def.measures.map((m) => ({ id: m.label, title: m.label })),
  ];

  const csvWriter = createObjectCsvWriter({
    path: path.join(outDir, def.outputFile),
    header: headers,
  });

  const records = rows.map((row) => {
    const record = {};
    headers.forEach((h, i) => {
      // qText trae el valor formateado como texto; qNum el numero crudo.
      // Para medidas uso qNum cuando existe (mejor para calculos posteriores).
      const cell = row[i];
      record[h.id] = (cell.qNum !== undefined && cell.qNum !== 'NaN') ? cell.qNum : cell.qText;
    });
    return record;
  });

  await csvWriter.writeRecords(records);
  console.log(`  Guardado en: output/${def.outputFile} (${records.length} filas)`);
}

async function main() {
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js. Corre primero "npm run list-apps".');
    process.exit(1);
  }

  console.log('Conectando a la app...');
  const { session, app } = await openApp(config.appId);
  console.log('Conectado. Iniciando extracciones:\n');

  for (const def of extractions) {
    const rows = await extractOne(app, def);
    await saveToCsv(def, rows);
  }

  await session.close();
  console.log('\nListo.');
}

main().catch((err) => {
  console.error('Error durante la extraccion:', err.message || err);
  process.exit(1);
});