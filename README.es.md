<p align="center">
  <img src="docs/screenshots/ogm-logo.png" alt="Logo de OpenMenu GDEMU Manager" width="120">
</p>

# OpenMenu GDEMU Manager (OGM)

[English](README.md)

Aplicacion portable para Windows para preparar y administrar tarjetas SD o respaldos locales de Dreamcast GDEMU/OpenMenu.

La app permite revisar una estructura GDEMU/OpenMenu, agregar o quitar juegos, compactar carpetas, reconstruir el menu OpenMenu, sincronizar caratulas y aplicar escritura solo cuando el diagnostico de seguridad lo permite.

## Estado

Beta publica. El flujo principal de SD ya fue probado en hardware real Dreamcast/GDEMU, incluyendo operaciones grandes de agregar, eliminar y actualizar caratulas. Aun asi, usala con respaldos y revisa siempre el diagnostico antes de aplicar cambios en una SD.

Este repositorio no incluye ROMs, BIOS, datos comerciales de juegos, respaldos de SD, assets oficiales de Sega ni credenciales privadas de APIs.

## Descargar

Descarga el ZIP portable para Windows desde [GitHub Releases](https://github.com/OlemOdracir/openmenu-gdemu-manager/releases).

Extrae el ZIP completo y ejecuta:

```text
OpenMenuGDEMUManager.exe
```

La app guarda configuracion, logs, cache y archivos generados dentro de la carpeta portable `data/`, junto al ejecutable.

Esta beta no esta firmada digitalmente. Windows SmartScreen puede mostrar una advertencia la primera vez que la abras.

## Capturas

### Ventana principal

![Ventana principal de OpenMenu GDEMU Manager](docs/screenshots/main-window.png)

### Fuentes online de caratulas

![Configuracion de fuentes online de caratulas](docs/screenshots/online-sources.png)

## Funciones

- Validacion segura de rutas antes de escribir.
- Deteccion de estructura GDEMU/OpenMenu.
- Instalar OpenMenu base en una SD FAT32 limpia usando assets incluidos.
- Administracion visual de juegos y caratulas.
- Agregar juegos GDI/CDI a slots numerados.
- Marcar juegos para eliminar y moverlos a una papelera interna de la SD.
- Compactar carpetas fisicas desde `02` para evitar huecos en OpenMenu.
- Reconstruir la carpeta `01` de OpenMenu con `buildgdi.exe`, sin parchear bloques fijos dentro de `track05.iso`.
- Leer caratulas existentes desde los DAT del menu en la SD.
- Guardar un registro liviano en `_openmenu_gdemu_manager/`.
- Busqueda de caratulas mediante fuentes locales y OpenMenu Cover API.
- Modo portable sin instalador.
- Interfaz en espanol e ingles.
- Comprobacion de nuevas versiones desde GitHub Releases.

## Seguridad y respaldos

La app no formatea tarjetas SD y no borra juegos inmediatamente durante el guardado normal. Los juegos eliminados se mueven a:

```text
_openmenu_gdemu_manager/trash/
```

Antes de reemplazar el menu OpenMenu, la app crea un backup tecnico automatico de la carpeta `01`. El backup completo de la SD sigue siendo opcional, pero se recomienda antes de operaciones grandes.

No desconectes la SD ni apagues el PC mientras se aplican cambios.

## Uso desde codigo fuente

Requisitos:

- Windows
- Python 3.11 o superior

```powershell
py -m pip install -e ".[dev]"
py -m openmenu_gdemu_manager
```

Para pruebas:

```powershell
py -m pytest
```

## Build portable

```powershell
$Version = "0.2.0-beta.3"
.\scripts\build_portable.ps1 -Version $Version
```

El resultado queda en `dist/`.

Para validar una release completa:

```powershell
$Version = "0.2.0-beta.3"
.\scripts\test_release.ps1 -Version $Version
```

## Fuentes online

La fuente recomendada es OpenMenu Cover API. No requiere cuenta de usuario y no expone credenciales privadas a la app de escritorio.

ScreenScraper directo queda como opcion avanzada para usuarios que quieran configurar sus propias credenciales. Otras fuentes estan reservadas para versiones futuras.

## Limitaciones de la beta

- No incluye juegos, BIOS, datos comerciales de juegos ni imagenes de SD.
- Incluye assets base OpenMenu GPL minimos usados solo para preparar la carpeta `01`.
- No formatea tarjetas SD.
- No esta firmada digitalmente; Windows SmartScreen puede mostrar una advertencia.
- Las pruebas de integracion contra la API publica se omiten por defecto y se ejecutan solo con `OPENMENU_RUN_INTEGRATION=1`.

## Documentacion

- [Guia de usuario](docs/USER_GUIDE.es.md)
- [Preguntas frecuentes](docs/FAQ.es.md)
- [Seguridad](SECURITY.md)
- [Contribuir](CONTRIBUTING.md)

## Contacto

[GitHub Issues](https://github.com/OlemOdracir/openmenu-gdemu-manager/issues)

## Licencia

OpenMenu GDEMU Manager se publica bajo GPL-3.0-or-later. Ver [LICENSE](LICENSE).
