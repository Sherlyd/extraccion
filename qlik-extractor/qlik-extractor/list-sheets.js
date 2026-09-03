// list-sheets.js
// Lista todas las hojas (sheets) de la app, con su ID y titulo. Solo
// lectura. Sirve para encontrar el ID de la hoja "Detalle Colchon" (o
// como se llame realmente) y despues inspeccionar sus objetos con
// get-sheet-objects.js.
//
// Uso: node list-sheets.js

const config = require('./config');
const { openApp } = require('./qlik-session');

async function main() {
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js.');
    process.exit(1);
  }

  const { session, app } = await openApp(config.appId);

  const obj = await app.createSessionObject({
    qInfo: { qType: 'SheetList' },
    qAppObjectListDef: {
      qType: 'sheet',
      qData: { title: '/qMetaDef/title' },
    },
  });

  const layout = await obj.getLayout();
  const hojas = layout.qAppObjectList.qItems;

  console.log(`\nSe encontraron ${hojas.length} hojas:\n`);
  hojas.forEach((h) => {
    const titulo = (h.qData && h.qData.title) || '(sin titulo)';
    console.log(`- ${titulo}`);
    console.log(`    ID: ${h.qInfo.qId}`);
  });

  await session.close();
}

main().catch((err) => {
  console.error('Error:', err.message || err);
  process.exit(1);
});