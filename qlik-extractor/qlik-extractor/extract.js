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
    name: 'ventas_por_producto',
    dimensions: ['Fecha de Alta', 'Tipo Comp', 'Distr.', 'Razon Social Distr', 'Razon Social CF',
             'Artículo', 'Familia1', 'Ejecutivo de Cuenta', 'Suc.'],
    measures: [
      { label: 'TotalVentas', expr: 'Sum(Ventas)' },
      { label: 'CantidadPedidos', expr: 'Count(DISTINCT IdPedido)' },
    ],
    outputFile: 'ventas_por_producto.csv',
  },
  // Ejemplo de una segunda extraccion:
  // {
  //   name: 'clientes_activos',
  //   dimensions: ['Cliente', 'Region'],
  //   measures: [
  //     { label: 'MontoTotal', expr: 'Sum(Monto)' },
  //   ],
  //   outputFile: 'clientes_activos.csv',
  // },
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

  const allRows = [];
  for (let top = 0; top < totalRows; top += PAGE_SIZE) {
    const height = Math.min(PAGE_SIZE, totalRows - top);
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
