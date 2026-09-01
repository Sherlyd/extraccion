// qlik-session.js
// Modulo compartido: Arma la sesion de enigma.js contra el Engine API.
// Lo usan connect.js, list-apps.js, list-fields.js y extract.js.

const fs = require('fs');
const path = require('path');
const WebSocket = require('ws');
const enigma = require('enigma.js');
const config = require('./config');

// -----------------------------------------------------------------------
// SCHEMA: enigma.js necesita el JSON de esquema que corresponde a la
// version del motor de Qlik. Para May 2024 Patch 8 todavia no confirmo
// el numero exacto (Qlik no publica una tabla 1 a 1 clara para todas las
// versiones). Dos formas de resolverlo cuando tenga todo instalado:
//
//   1) node -e "console.log(require('fs').readdirSync('node_modules/enigma.js/schemas'))"
//      Esto lista los schemas que trae instalados enigma.js. Elejo el mas
//      cercano a la version de engine (14.187.13).
//
//   2) En el Dev Hub hay una pagina de "API Insights" que confirma la version exacta de API
//      que expone el servidor.
//
// El protocolo JSON-RPC de Qlik es retrocompatible: un schema levemente
// mas viejo que el engine real casi siempre funciona igual para lo basico
// (abrir apps, pedir hypercubes). Por eso dejo como default un schema
// ampliamente usado y estable; si algo no responde como se espera, es el
// primer lugar a revisar.
const schema = require('enigma.js/schemas/12.612.0.json');

function buildConfig(appId) {
  const certPath = path.resolve(__dirname, config.certsPath);

  return {
    schema,
    url: `wss://${config.engineHost}:${config.enginePort}/app/${appId || ''}`,
    createSocket: (url) => new WebSocket(url, {
      ca: [fs.readFileSync(path.join(certPath, 'root.pem'))],
      cert: fs.readFileSync(path.join(certPath, 'client.pem')),
      key: fs.readFileSync(path.join(certPath, 'client_key.pem')),
      headers: {
        'X-Qlik-User': `UserDirectory=${config.userDirectory}; UserId=${config.userId}`,
      },
      rejectUnauthorized: false, // el cert del servidor suele ser self-signed en client-managed
    }),
  };
}

// Se conecta a nivel global (sin abrir ninguna app todavia).
// Sirve para listar apps disponibles (getDocList).
async function openGlobalSession() {
  const session = enigma.create(buildConfig(''));
  const global = await session.open();
  return { session, global };
}

// Se conecta y abre una app puntual por su ID.
async function openApp(appId) {
  const session = enigma.create(buildConfig(appId));
  const global = await session.open();
  const app = await global.openDoc(appId);
  return { session, global, app };
}

module.exports = { openGlobalSession, openApp };
