# run_diario.ps1
# Encadena todo el proceso diario: extrae de Qlik, copia los CSV, y
# carga a la base propia. Pensado para que lo dispare el Task Scheduler
# de Windows, sin que nadie tenga que tocar nada a mano.
#
# IMPORTANTE: ajusta $baseDir mas abajo si tu carpeta "PROYECTO CRM" no
# esta exactamente en esa ruta.

# El Task Scheduler no siempre hereda el mismo PATH que tu terminal
# interactiva -- por eso "node" puede no encontrarse aunque funcione
# perfecto cuando lo corres vos a mano. Lo agregamos explicitamente.
$env:Path += ";C:\Program Files\nodejs"

$baseDir = "C:\Users\sletelier\OneDrive - johnsonacero.com\Escritorio\PROYECTO CRM"
$logDir = "$baseDir\logs"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$fecha = Get-Date -Format "yyyy-MM-dd_HHmm"
$logFile = "$logDir\extraccion_$fecha.log"

function Log($mensaje) {
    $linea = "$(Get-Date -Format 'HH:mm:ss')  $mensaje"
    Write-Host $linea
    Add-Content -Path $logFile -Value $linea
}

Log "===== Extraccion diaria iniciada ====="

try {
    Set-Location "$baseDir\qlik-extractor\qlik-extractor"
    Log "Corriendo extract.js..."
    $salidaExtract = node extract.js 2>&1
    $salidaExtract | Add-Content -Path $logFile
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: extract.js fallo (codigo $LASTEXITCODE). No se continua con la carga."
        exit 1
    }

    Set-Location "$baseDir\reportes-piletas"
    Log "Copiando los CSV generados..."
    Copy-Item "..\qlik-extractor\qlik-extractor\output\facturacion_detalle.csv" "data\" -Force
    Copy-Item "..\qlik-extractor\qlik-extractor\output\pedidos_detalle.csv" "data\" -Force
    Copy-Item "..\qlik-extractor\qlik-extractor\output\cartera_pendiente.csv" "data\" -Force

    Log "Cargando datos a la base..."
    # Uso el python del entorno virtual directamente (sin "activar"),
    # que es lo que funciona de forma confiable cuando lo dispara el
    # Task Scheduler sin que haya una sesion interactiva de por medio.
    $salidaCarga = & "$baseDir\.venv\Scripts\python.exe" cargar_datos.py 2>&1
    $salidaCarga | Add-Content -Path $logFile
    if ($LASTEXITCODE -ne 0) {
        Log "ERROR: cargar_datos.py fallo (codigo $LASTEXITCODE)."
        exit 1
    }

    Log "===== Extraccion diaria finalizada correctamente ====="
}
catch {
    Log "ERROR INESPERADO: $_"
    exit 1
}
