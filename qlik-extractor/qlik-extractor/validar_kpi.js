// validar_kpi.js
// Calcula el mismo indicador "Facturacion" que usa el dashboard de
// Qlik, pero desde una sesion propia via API -- no depende de ni toca
// la sesion de nadie mas en el navegador. Sirve para validar el total
// sin necesitar acceso de edicion en Qlik.
//
// Uso: node validar_kpi.js

const config = require('./config');
const { openApp } = require('./qlik-session');

async function main() {
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js.');
    process.exit(1);
  }

  const { session, app } = await openApp(config.appId);

  // Misma expresion exacta que usa el KPI "Facturacion" del dashboard
  // (confirmada antes via list-master-measures.js).
  const obj = await app.createSessionObject({
    qInfo: { qType: 'validacion' },
    qHyperCubeDef: {
      qDimensions: [],
      qMeasures: [
        { qDef: { qDef: "Sum({<_Documento={'Factura'}>} #Facturacion)" } },
      ],
      qInitialDataFetch: [{ qTop: 0, qLeft: 0, qHeight: 1, qWidth: 1 }],
    },
  });

  const layout = await obj.getLayout();
  const valor = layout.qHyperCube.qDataPages[0].qMatrix[0][0];

  console.log('Facturacion total segun la MISMA expresion del dashboard de Qlik:');
  console.log('  Numero:', valor.qNum);
  console.log('  Texto: ', valor.qText);
  console.log('\nEsta sesion es propia (via API), sin ningun filtro aplicado --');
  console.log('no depende de la sesion de nadie mas.');
  console.log('Compara este numero contra la suma de la columna "Importe" en facturacion_detalle.xlsx');

  await session.close();
}

main().catch((err) => {
  console.error('Error:', err.message || err);
  process.exit(1);
});