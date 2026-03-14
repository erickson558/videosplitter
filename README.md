# VideoSplitter V1.0.0

Aplicacion de escritorio en Python para dividir un video en partes numeradas por tiempo o en partes iguales, y convertir cada parte al formato deseado.

## Resultado de salida

Para un archivo `MiVideo.mp4`, genera:

- `MiVideo Parte 1.mp4`
- `MiVideo Parte 2.mp4`
- `MiVideo Parte 3.mp4`

Cada parte se exporta segun tres selecciones en la interfaz:

- Modo de division:
- `Por segundos`
- `Partes iguales` indicando cuantas partes deseas generar

- Perfil de video:
- `Short 9:16 (1080x1920)` para Shorts de YouTube
- `Normal 16:9 (1920x1080)` para salida horizontal
- `Original (sin redimensionar)`

- Contenedor:
- `MP4`
- `MKV`
- `MOV`

Codificacion:

- Video `H.264`
- Audio `AAC`

## Ejecucion en desarrollo

```powershell
python main.py
```

## Compilacion a EXE

```powershell
python build_exe.py
```

El script:

- Usa el primer archivo `.ico` que encuentre en la carpeta del proyecto.
- Si no hay `.ico`, crea `videosplitter.ico`.
- Descarga FFmpeg automaticamente si no existe en `third_party/ffmpeg`.
- Incluye `ffmpeg.exe` y `ffprobe.exe` dentro del ejecutable final.
- Inserta la version `1.0.0` en los metadatos del `.exe`.
- Genera `VideoSplitter.exe` en esta misma carpeta.
- El primer build requiere internet para descargar FFmpeg.

## Modo silencioso

La app ejecuta FFmpeg y FFprobe en segundo plano sin mostrar ventana CMD.

## Correccion de progreso N/A

Si FFmpeg devuelve valores `N/A` durante el progreso, la app los ignora sin fallar.

## Requisitos

- Python 3.10+
- FFmpeg no es obligatorio en el sistema para el `.exe` generado (queda embebido).
- (Opcional) FFprobe para progreso exacto

## Si FFmpeg no esta instalado

La app incluye boton `Configurar FFmpeg...` para seleccionar manualmente `ffmpeg.exe`.
La ruta queda guardada en `videosplitter.settings.json` junto al ejecutable.

## Configuracion persistente

El archivo `videosplitter.settings.json` guarda:

- Ruta de `ffmpeg.exe` y `ffprobe.exe`
- Modo de division seleccionado
- Segundos por parte
- Cantidad de partes iguales
- Perfil de video y contenedor seleccionados
- Carpeta de salida usada mas recientemente
