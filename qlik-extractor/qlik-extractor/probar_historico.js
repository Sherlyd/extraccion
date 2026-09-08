// probar_historico.js
// Prueba diagnostica: extrae SOLO Año + Mes + facturacion total, sin
// ninguno de los campos de detalle de "Datos FC" (cliente, articulo,
// distribuidor). Sirve para confirmar si el historico completo existe
// a nivel agregado aunque el detalle linea por linea solo tenga
// cargados los meses recientes.
//
// Uso: node probar_historico.js

const config = require('./config');
const { openApp } = require('./qlik-session');

async function main() {
  const { session, app } = await openApp(config.appId);
  await app.clearAll();

  const campoDocumento = await app.getField('_Documento');
  await campoDocumento.selectValues([{ qText: 'Factura' }], false, true);

  const obj = await app.createSessionObject({
    qInfo: { qType: 'prueba-historico' },
    qHyperCubeDef: {
      qDimensions: [
        { qDef: { qFieldDefs: ['Año'] } },
        { qDef: { qFieldDefs: ['Mes'] } },
      ],
      qMeasures: [
        { qDef: { qDef: "Sum({<_Documento={'Factura'}>} #Facturacion)" } },
      ],
      qInitialDataFetch: [{ qTop: 0, qLeft: 0, qHeight: 200, qWidth: 3 }],
      qSuppressMissing: false,
      qSuppressZero: false,
    },
  });

  const layout = await obj.getLayout();
  const filas = layout.qHyperCube.qDataPages[0].qMatrix;

  console.log(`\nSe encontraron ${filas.length} combinaciones Año/Mes con facturacion:\n`);
  filas.forEach((f) => {
    console.log(`  ${f[0].qText}-${f[1].qText.padStart(2, '0')}: ${f[2].qText}`);
  });

  await session.close();
}

main().catch((err) => {
  console.error('Error:', err.message || err);
  process.exit(1);
});