// get-sheet-objects.js
// Dado el ID de una hoja (sacado de list-sheets.js), lista los objetos
// que contiene (tablas, graficos) y muestra sus medidas y dimensiones.
// Resuelve tanto expresiones escritas directo en el objeto como las que
// referencian un elemento MAESTRO (measure/dimension reutilizable) via
// qLibraryId -- en ese caso busca la definicion real del maestro.
// Solo lectura, no modifica nada en Qlik.
//
// Uso: node get-sheet-objects.js <sheetId>

const config = require('./config');
const { openApp } = require('./qlik-session');

const sheetId = process.argv[2];

async function resolverDimension(app, d) {
  if (d.qDef && d.qDef.qFieldDefs && d.qDef.qFieldDefs.length) {
    return `  Dimension: ${d.qDef.qFieldDefs.join(', ')}`;
  }
  if (d.qLibraryId) {
    try {
      const dimObj = await app.getDimension(d.qLibraryId);
      const dimProps = await dimObj.getProperties();
      const nombre = (dimProps.qMetaDef && dimProps.qMetaDef.title) || '(sin nombre)';
      const campos = (dimProps.qDim && dimProps.qDim.qFieldDefs) || [];
      return `  Dimension (maestra "${nombre}"): ${campos.join(', ')}`;
    } catch (e) {
      return `  Dimension (maestra, id ${d.qLibraryId}) -- no se pudo resolver: ${e.message}`;
    }
  }
  return '  Dimension: (vacia o sin datos legibles)';
}

async function resolverMedida(app, m) {
  if (m.qDef && m.qDef.qDef) {
    return `  Medida: ${m.qDef.qLabel || '(sin etiqueta)'}\n    Expresion: ${m.qDef.qDef}`;
  }
  if (m.qLibraryId) {
    try {
      const measObj = await app.getMeasure(m.qLibraryId);
      const measProps = await measObj.getProperties();
      const nombre = (measProps.qMetaDef && measProps.qMetaDef.title) || '(sin nombre)';
      const expr = (measProps.qMeasure && measProps.qMeasure.qDef) || '(sin expresion)';
      return `  Medida (maestra "${nombre}"):\n    Expresion: ${expr}`;
    } catch (e) {
      return `  Medida (maestra, id ${m.qLibraryId}) -- no se pudo resolver: ${e.message}`;
    }
  }
  return '  Medida: (sin definicion legible)';
}

async function main() {
  if (!sheetId) {
    console.error('Uso: node get-sheet-objects.js <sheetId>');
    process.exit(1);
  }
  if (!config.appId) {
    console.error('Falta definir "appId" en config.js.');
    process.exit(1);
  }

  const { session, app } = await openApp(config.appId);
  const sheet = await app.getObject(sheetId);
  const layout = await sheet.getLayout();

  const celdas = layout.cells || [];
  console.log(`\nHoja: "${layout.qMeta.title}"  (${celdas.length} objetos)\n`);

  for (const celda of celdas) {
    try {
      const objeto = await app.getObject(celda.name);
      const props = await objeto.getProperties();
      const tipo = props.qInfo.qType;
      const titulo = props.title || (props.qMetaDef && props.qMetaDef.title) || '(sin titulo)';

      console.log(`--- ${titulo}  (tipo: ${tipo}, id: ${celda.name}) ---`);

      if (props.qHyperCubeDef) {
        for (const d of props.qHyperCubeDef.qDimensions || []) {
          console.log(await resolverDimension(app, d));
        }
        for (const m of props.qHyperCubeDef.qMeasures || []) {
          console.log(await resolverMedida(app, m));
        }
      } else {
        console.log('  (este objeto no tiene un hypercube directo -- puede ser texto, filtro, o un tipo especial)');
      }
      console.log('');
    } catch (e) {
      console.log(`  (no se pudo leer este objeto: ${e.message})\n`);
    }
  }

  await session.close();
}

main().catch((err) => {
  console.error('Error:', err.message || err);
  process.exit(1);
});