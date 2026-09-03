// list-field-values.js
// Muestra los valores distintos que toma un campo puntual dentro de la
// app. Sirve para decidir, por ejemplo, si "Rubro" o "Familia1" es el
// campo correcto para identificar Piletas, viendo que valores reales
// contiene cada uno (en vez de adivinar por el nombre del campo).
//
// Uso: node list-field-values.js "Rubro"
//      node list-field-values.js "Familia1"
//      node list-field-values.js "Plan Piletas"

const config = require('./config');
const { openApp } = require('./qlik-session');

const nombreCampo = process.argv[2];

async function main() {
  if (!nombreCampo) {
    console.error('Uso: node list-field-values.js "Nombre Del Campo"');
    process.exit(1);
  }
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js.');
    process.exit(1);
  }

  const { session, app } = await openApp(config.appId);

  const obj = await app.createSessionObject({
    qInfo: { qType: 'valores-campo' },
    qListObjectDef: {
      qDef: { qFieldDefs: [nombreCampo] },
      qInitialDataFetch: [{ qTop: 0, qLeft: 0, qHeight: 2000, qWidth: 1 }],
    },
  });

  const layout = await obj.getLayout();
  const valores = layout.qListObject.qDataPages[0].qMatrix;

  console.log(`\nValores distintos de "${nombreCampo}" (${valores.length} encontrados):\n`);
  valores.forEach((fila) => {
    console.log(`  - ${fila[0].qText}`);
  });

  await session.close();
}

main().catch((err) => {
  console.error('Error:', err.message || err);
  process.exit(1);
});