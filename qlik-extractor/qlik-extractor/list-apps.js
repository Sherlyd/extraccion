// list-apps.js
// Lista todas las apps visibles para el usuario de servicio, con su ID.
// lo uso para encontrar el appId que despues pongo en config.js.
//
// Uso: npm run list-apps

const { openGlobalSession } = require('./qlik-session');

async function main() {
  const { session, global } = await openGlobalSession();

  const apps = await global.getDocList();

  console.log(`\nSe encontraron ${apps.length} apps:\n`);
  apps.forEach((app) => {
    console.log(`- ${app.qTitle}`);
    console.log(`    ID: ${app.qDocId}`);
    console.log(`    Stream: ${app.qMeta && app.qMeta.stream ? app.qMeta.stream.name : '(personal)'}`);
    console.log('');
  });

  await session.close();
}

main().catch((err) => {
  console.error('Error al listar apps:', err.message || err);
  process.exit(1);
});
