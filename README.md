# VideoSplitter V1.0.2

![VideoSplitter banner](docs/assets/banner.svg)

Aplicacion de escritorio en Python para dividir videos en segmentos numerados, ya sea por duracion fija o en partes iguales, con salida en MP4, MKV o MOV y perfiles listos para Shorts o video horizontal.

## Vista del producto

### Pantalla principal

![Pantalla principal](docs/assets/screenshot-main.svg)

### Modo partes iguales

![Modo partes iguales](docs/assets/screenshot-equal-parts.svg)

## Que hace el programa

- Permite seleccionar un video de entrada desde la GUI.
- Permite dividirlo por cantidad de segundos o por cantidad de partes iguales.
- Convierte cada salida a H.264 + AAC.
- Permite escoger perfil de video: Short 9:16, Normal 16:9 u Original.
- Permite escoger contenedor: MP4, MKV o MOV.
- Guarda configuraciones persistentes en `videosplitter.settings.json`.
- Genera un ejecutable `.exe` en Windows con FFmpeg embebido.

## Ejemplo de salida

Para un archivo `MiVideo.mp4`, genera archivos como:

- `MiVideo Parte 1.mp4`
- `MiVideo Parte 2.mp4`
- `MiVideo Parte 3.mp4`

## Tecnologias

- Python 3.12
- Tkinter para la interfaz grafica
- FFmpeg y FFprobe para procesamiento multimedia
- PyInstaller para empaquetado del `.exe`

## Requisitos

- Windows para compilar el `.exe`
- Python 3.10 o superior
- Git y GitHub CLI (`gh`) para automatizar releases

## Dependencias

Dependencias de build:

```powershell
pip install -r requirements-build.txt
```

Actualmente la app no requiere dependencias externas para ejecutar el codigo fuente fuera de las herramientas de build.

## Tests automaticos

Los tests unitarios cubren validacion de configuracion, persistencia de settings, generacion de comandos FFmpeg y construccion de release notes.

```powershell
python -m unittest discover -s tests -v
```

## Ejecutar en desarrollo

```powershell
python main.py
```

## Compilar el ejecutable

```powershell
python build_exe.py
```

El script de build:

- Usa el `.ico` que encuentre en la raiz del proyecto.
- Descarga FFmpeg si no existe en `third_party/ffmpeg`.
- Inserta la version actual en los metadatos del `.exe`.
- Genera `VideoSplitter.exe` en la carpeta raiz del proyecto.

## Configuracion persistente

El archivo `videosplitter.settings.json` guarda:

- Ruta de `ffmpeg.exe`
- Ruta de `ffprobe.exe`
- Version actual de la app
- Modo de division seleccionado
- Segundos por parte
- Cantidad de partes iguales
- Perfil de video
- Contenedor de salida
- Carpeta de salida mas reciente

## Versionado

El proyecto usa versionado semantico en formato `Vx.x.x`.

Regla recomendada:

- `patch`: correcciones, ajustes menores, documentacion o mejoras internas
- `minor`: nuevas funcionalidades compatibles
- `major`: cambios incompatibles o redisenos importantes

## Release automatizada

Se incluye el script `scripts/release.py` para que cada commit de entrega:

- Incremente la version
- Actualice la app y la documentacion base
- Recompile `VideoSplitter.exe`
- Cree el commit
- Cree el tag Git
- Haga push a `main`
- Cree la Release en GitHub
- Adjunte el `.exe` compilado a la release
- Genere Release Notes personalizadas con highlights, commits y archivos clave

Ejemplos:

```powershell
python scripts/release.py "chore: release Vx.x.x"
python scripts/release.py "feat: nueva funcionalidad" --level minor
python scripts/release.py "feat!: cambio incompatible" --level major
python scripts/release.py "docs: actualiza documentacion" --skip-build-exe
```

## Comandos manuales paso a paso

Crear repo local:

```powershell
git init -b main
```

Agregar archivos:

```powershell
git add .
```

Crear commit:

```powershell
git commit -m "feat: mensaje descriptivo"
```

Crear repo remoto publico con GitHub CLI:

```powershell
gh repo create videosplitter --public --source=. --remote=origin
```

Subir rama principal:

```powershell
git push -u origin main
```

Crear tag de version:

```powershell
git tag -a v1.0.0 -m "Release V1.0.0"
git push origin v1.0.0
```

Crear release en GitHub:

```powershell
gh release create v1.0.0 --title "V1.0.0" --notes-file release-notes.md
```

## Buenas practicas del repositorio

- Licencia Apache 2.0 incluida en `LICENSE`
- CI en GitHub Actions para validar sintaxis y tests unitarios
- Dependabot configurado para revisar dependencias y workflows
- `.gitignore` para excluir binarios y artefactos generados
- Version unica centralizada en `app_metadata.py`
- Assets visuales en `docs/assets/` para documentacion del producto

## Licencia

Este proyecto esta distribuido bajo Apache License 2.0. Consulta el archivo `LICENSE`.
