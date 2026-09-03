// list-master-measures.js
// Lista todas las medidas maestras (reutilizables) de la app, con su
// expresion real. Es de SOLO LECTURA -- no modifica nada en Qlik, no
// requiere entrar a editar ninguna hoja. Sirve para conseguir la formula
// exacta de indicadores como "Total Pendiente" o "Importe Neto" sin
// necesitar permisos de edicion ni tocar la cuenta de nadie.
//
// Uso: node list-master-measures.js

const config = require('./config');
const { openApp } = require('./qlik-session');

async function main() {
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js.');
    process.exit(1);
  }

  const { session, app } = await openApp(config.appId);

  const obj = await app.createSessionObject({
    qInfo: { qType: 'MeasureList' },
    qMeasureListDef: {
      qType: 'measure',
      qData: { title: '/qMetaDef/title', tags: '/qMetaDef/tags' },
    },
  });

  const layout = await obj.getLayout();
  const medidas = layout.qMeasureList.qItems;

  console.log(`\nSe encontraron ${medidas.length} medidas maestras:\n`);

  for (const m of medidas) {
    const measureObj = await app.getMeasure(m.qInfo.qId);
    const props = await measureObj.getProperties();
    console.log(`- ${props.qMetaDef.title}`);
    console.log(`    Expresion: ${props.qMeasure.qDef}`);
    if (props.qMeasure.qLabel) console.log(`    Etiqueta:   ${props.qMeasure.qLabel}`);
    console.log('');
  }

  if (medidas.length === 0) {
    console.log('No hay medidas maestras en esta app -- probablemente las');
    console.log('expresiones estan escritas directo dentro de cada grafico.');
    console.log('En ese caso hace falta el script list-sheet-objects.js (avisame).');
  }

  await session.close();
}

main().catch((err) => {
  console.error('Error:', err.message || err);
  process.exit(1);
});