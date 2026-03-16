# Guia de contribucion

Gracias por tu interes en contribuir a VideoSplitter. Esta guia explica como configurar el entorno, que convenciones seguir y como enviar un Pull Request correctamente.

---

## Prerrequisitos

- Python 3.10+ (recomendado 3.12)
- Git
- FFmpeg disponible en el PATH o en `third_party/ffmpeg/` (requerido para el test de integracion)

---

## Configuracion local

```powershell
git clone https://github.com/erickson558/videosplitter.git
cd videosplitter

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements-build.txt
```

---

## Tests

Antes de enviar cualquier cambio, asegurate de que toda la suite pase:

```powershell
python -m unittest discover -s tests -v
```

Agrega test unitarios para cada cambio nuevo de comportamiento. El test de integracion en `tests/test_integration_split.py` se ejecuta con FFmpeg real; es saltado automaticamente si FFmpeg no esta disponible en el entorno.

---

## Convenciones de commits

Se usa [Conventional Commits](https://www.conventionalcommits.org/):

| Prefijo | Cuando usarlo |
|---|---|
| `feat:` | Nueva funcionalidad |
| `fix:` | Correccion de bug |
| `docs:` | Cambios solo de documentacion |
| `test:` | Agregar o corregir tests |
| `build:` | Cambios en el sistema de build o dependencias |
| `chore:` | Mantenimiento, refactor menor, limpieza |
| `perf:` | Mejoras de rendimiento |

Ejemplos:

```
feat: add GPU device selector with CPU fallback
fix: handle missing ffprobe gracefully on probe_duration
docs: expand README with GPU configuration table
test: cover explicit NVENC GPU index mapping
```

---

## Flujo de trabajo

1. Haz fork del repositorio y crea una rama desde `main`:

   ```powershell
   git checkout -b feat/mi-funcionalidad
   ```

2. Implementa el cambio con tests.

3. Verifica que la suite pase completa.

4. Haz push a tu fork y abre un **Pull Request** contra `main` de este repositorio.

5. Describe en el PR _que_ cambia, _por que_ y cualquier consideracion de compatibilidad.

---

## Versionado

La version esta centralizada en `app_metadata.py`. No la modifiques manualmente en un PR: el mantenedor la incrementa al hacer merge usando `scripts/release.py`.

---

## Estructura de los tests

| Archivo | Que cubre |
|---|---|
| `test_models.py` | Validacion de `SplitJobConfig` |
| `test_settings.py` | Persistencia de settings y retrocompatibilidad de campos |
| `test_video_splitter_service.py` | Generacion de comandos FFmpeg, seleccion de encoder GPU, opciones de procesamiento |
| `test_release.py` | Clasificacion de commits, render de release notes, normalizacion de URL |
| `test_integration_split.py` | Split de extremo a extremo con video sintetico real |

---

## Licencia

Al contribuir aceptas que tu aporte sea distribuido bajo [Apache License 2.0](LICENSE).
