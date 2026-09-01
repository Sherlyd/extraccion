// list-fields.js
// Una vez que defino el appId en config.js, este script muestra
// todos los campos que existen dentro de esa app (nombres exactos,
// necesarios para armar el hypercube en extract.js).
//
// Uso: npm run list-fields

const config = require('./config');
const { openApp } = require('./qlik-session');

async function main() {
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js. Corre primero "npm run list-apps".');
    process.exit(1);
  }

  const { session, app } = await openApp(config.appId);

  const fieldListObj = await app.createSessionObject({
    qInfo: { qType: 'FieldList' },
    qFieldListDef: { qShowSystem: false, qShowHidden: false, qShowSemantic: true, qShowSrcTables: true },
  });

  const layout = await fieldListObj.getLayout();
  const fields = layout.qFieldList.qItems;

  console.log(`\nSe encontraron ${fields.length} campos en la app:\n`);
  fields.forEach((f) => {
    console.log(`- ${f.qName}  (tabla origen: ${f.qSrcTables ? f.qSrcTables.join(', ') : '?'})`);
  });

  await session.close();
}

main().catch((err) => {
  console.error('Error al listar campos:', err.message || err);
  process.exit(1);
});
