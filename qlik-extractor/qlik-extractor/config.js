// config.js
// Datos de conexion al servidor de Qlik Sense Enterprise.


module.exports = {
  engineHost: 'qvserver1.johnson.net',

  // Puerto del motor QIX. El estandar es 4747 (no confundir con el 443 del hub/QMC), igual revisar documentacion
  enginePort: 4747,

  // ID de la app. Se obtiene de la URL cuando abris la app
  // en el hub: .../sense/app/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX/...
  // Dejalo vacio ('') para list-apps.js, que muestra todas las apps disponibles.
  appId: 'ccc7e750-8f3c-42cc-b495-1ec7bca0fd0b',

  // Usuario "de servicio" con el que se conecta al motor.
  // Pedir al admin cual usar. Un valor tipico por defecto es:
  userDirectory: 'JOHNSON',
  userId: 'rgonzalez',

  // Carpeta donde se va a copiar los 3 archivos que entreguen:
  // client.pem, client_key.pem, root.pem
  certsPath: './certs',

  // Carpeta donde se guardan los CSV generados por extract.js
  outputPath: './output',
};
