// list-variables.js
// Lista todas las variables de la app con su definicion real. Muchas
// medidas usan variables como $(vMesActualIni), $(vYTDIni), etc -- sin
// saber que contienen, no podemos replicar correctamente la logica de
// "mes actual", "YTD", etc en nuestro propio codigo. Solo lectura.
//
// Uso: node list-variables.js

const config = require('./config');
const { openApp } = require('./qlik-session');

async function main() {
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js.');
    process.exit(1);
  }

  const { session, app } = await openApp(config.appId);

  const obj = await app.createSessionObject({
    qInfo: { qType: 'VariableList' },
    qVariableListDef: {
      qType: 'variable',
      qShowReserved: false,
      qShowConfig: false,
      qData: { definition: '/qDefinition' },
    },
  });

  const layout = await obj.getLayout();
  const variables = layout.qVariableList.qItems;

  console.log(`\nSe encontraron ${variables.length} variables:\n`);
  variables.forEach((v) => {
    console.log(`- ${v.qName}`);
    console.log(`    ${v.qDefinition}`);
    console.log('');
  });

  await session.close();
}

main().catch((err) => {
  console.error('Error:', err.message || err);
  process.exit(1);
});