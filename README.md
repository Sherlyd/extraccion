# Qlik Extractor

Script en Node.js para conectarse al Engine API de **Qlik Sense Enterprise
on Windows** (client-managed) via `enigma.js`, extraer datos de una app y
guardarlos en CSV para usarlos en su propio analisis/CRM.

Servidor objetivo: `qvserver1.johnson.net`
Version detectada: Qlik Sense May 2024 Patch 8 (engine 14.187.13)

## 0. Requisitos previos

- Node.js instalado (v18 o superior recomendado).
- Los 3 archivos de certificado exportados desde la QMC:
  `client.pem`, `client_key.pem`, `root.pem`.
- Un usuario de servicio confirmado (directory + userId) con permisos de
  lectura sobre las apps que se van a consultar.
- Que el puerto 4747 sea alcanzable desde donde se corra el script hacia
  el servidor de Qlik (si no corre en la misma red, hay que pedir que
  abran ese puerto).

## 1. Instalar dependencias

```bash
npm install
```

## 2. Copiar los certificados

Se debe copiar los 3 `.pem` dentro de la carpeta `certs/`
(reemplazando el archivo de texto que esta ahi de placeholder).

## 3. Completar config.js

Abrir `config.js` y confirmar/completar:

- `engineHost`: normalmente ya esta bien (`qvserver1.johnson.net`).
- `userDirectory` / `userId`: el usuario de servicio.
- `appId`: lo dejo vacio por ahora, lo lleno en el paso 5.

## 4. Probar la conexion

```bash
npm run test-connection
```

Si todo esta bien, va a imprimir la version del motor. Si falla, el
mensaje de error dice donde mirar (certificados, host, usuario, puerto).

## 5. Encontrar el ID de la app que se necesita

```bash
npm run list-apps
```

Esto lista todas las apps visibles con su ID. Copia el que interese
y pegarlo en `config.js` -> `appId`.

## 6. Ver los nombres exactos de los campos

```bash
npm run list-fields
```

Muestra todos los campos de la app elegida, con la tabla de origen.

## 7. Definir que extraer

Abrir `extract.js` y editar el array `extractions` al principio del
archivo: para cada conjunto de datos que uno quiera, definir dimensiones
(campos) y medidas (expresiones tipo `Sum(Campo)`, `Count(Campo)`, etc.),
usando los nombres exactos que se vio en el paso 6.

## 8. Extraer

```bash
npm run extract
```

Los CSV quedan en la carpeta `output/`, uno por cada extraccion definida.
Desde ahi los conecto a la base de datos, al motor de reportes, o donde se necesite

## 9. Automatizar

Una vez que el script funciona a mano, se automatiza como cualquier
script de Node: con el Task Scheduler de Windows, un cron si corre en
Linux, o un pipeline. Simplemente programa `npm run extract` con la
periodicidad que necesite (diario, cada hora, etc.).

## Notas sobre el schema de enigma.js

El archivo `qlik-session.js` usa un schema de enigma.js (`12.612.0.json`)
que no esta 100% confirmado contra la version exacta de motor. Si al
correr `test-connection` o cualquier otro script hay errores raros de
metodos "no reconocidos", revisa el comentario dentro de
`qlik-session.js`: ahi se explica como listar los schemas disponibles
instalados y como confirmar la version exacta via el Dev Hub.
