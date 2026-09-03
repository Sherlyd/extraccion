// list-tables.js
// Muestra la estructura COMPLETA del modelo de datos de la app: todas
// las tablas cargadas, sus campos, y como se asocian entre si (las
// claves que Qlik usa para vincular tablas). Esto va un nivel mas
// profundo que list-fields.js: te dice no solo que campos existen, sino
// como estan organizados y relacionados — util para saber que se puede
// cruzar sin duplicar filas, y para detectar tablas enteras que no se
// usan en ningun grafico visible del dashboard.
//
// Uso: node list-tables.js

const config = require('./config');
const { openApp } = require('./qlik-session');

async function main() {
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js.');
    process.exit(1);
  }

  const { session, app } = await openApp(config.appId);

  const modelo = await app.getTablesAndKeys(
    { qcx: 1000, qcy: 1000 },  // tamaño max de la matriz de vista (no relevante aca)
    { qcx: 0, qcy: 0 },
    30,     // qSignificanceLevel (irrelevante para este uso, valor por defecto)
    true,   // qIncludeSysVars
    false,  // qIncludeSrcTables -- false porque no necesitamos vista previa de datos, solo estructura
    true,   // qIncludeProfiling
  );

  console.log(`\n=== ${modelo.qtr.length} tablas encontradas en el modelo de datos ===\n`);

  modelo.qtr.forEach((tabla) => {
    console.log(`TABLA: ${tabla.qName}  (${tabla.qFields.length} campos, ${tabla.qNoOfRows} filas)`);
    tabla.qFields.forEach((campo) => {
      const clave = campo.qIsKey ? ' [CLAVE - se usa para asociar con otra tabla]' : '';
      console.log(`  - ${campo.qName}${clave}`);
    });
    console.log('');
  });

  if (modelo.qk && modelo.qk.length) {
    console.log('=== Asociaciones entre tablas (a traves de que campo se vinculan) ===\n');
    modelo.qk.forEach((asoc) => {
      console.log(`  ${asoc.qTables.join(' <-> ')}  via campo(s): ${asoc.qFieldNames.join(', ')}`);
    });
  } else {
    console.log('(No se encontraron asociaciones explicitas — puede que la app use un modelo desnormalizado en una sola tabla, o "synthetic keys" que Qlik resuelve internamente.)');
  }

  await session.close();
}

main().catch((err) => {
  console.error('Error al explorar el modelo de datos:', err.message || err);
  process.exit(1);
});