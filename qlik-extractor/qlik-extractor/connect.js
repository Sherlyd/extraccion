// connect.js
// Prueba minima: solo intenta conectarse y abrir sesion global.
// Correr primero, antes que cualquier otra cosa, para confirmar que
// certificados + usuario + servidor estan bien configurados.
//
// Uso: npm run test-connection

const { openGlobalSession } = require('./qlik-session');

async function main() {
  console.log('Conectando al motor de Qlik...');
  const { session, global } = await openGlobalSession();

  const engineVersion = await global.engineVersion();
  console.log('Conexion exitosa.');
  console.log('Version del motor:', engineVersion.qComponentVersion);

  await session.close();
}

main().catch((err) => {
  console.error('Fallo la conexion:', err.message || err);
  console.error('\nRevisa: 1) rutas de los .pem en ./certs, 2) engineHost/enginePort en config.js,');
  console.error('3) que el usuario X-Qlik-User tenga permisos, 4) si el server no es alcanzable en el puerto 4747 desde tu red.');
  process.exit(1);
});
