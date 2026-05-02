<p align="center">
  <img src="docs/screenshots/ogm-logo.png" alt="Logo de OpenMenu GDEMU Manager" width="120">
</p>

# OpenMenu GDEMU Manager (OGM)

[English](README.md)

Aplicacion portable para Windows para preparar y administrar tarjetas SD o respaldos locales de Dreamcast GDEMU/OpenMenu.

La app permite revisar una estructura GDEMU/OpenMenu, organizar juegos, buscar caratulas, preparar cambios y aplicar escritura solo cuando el diagnostico de seguridad lo permite.

## Estado

Beta publica temprana. Usala con respaldos y revisa siempre el diagnostico antes de aplicar cambios en una SD.

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
- Administracion visual de juegos y caratulas.
- Busqueda de caratulas mediante fuentes locales y OpenMenu Cover API.
- Modo portable sin instalador.
- Comprobacion de nuevas versiones desde GitHub Releases.

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
.\scripts\build_portable.ps1 -Version 0.1.0
```

El resultado queda en `dist/`.

Para validar una release completa:

```powershell
.\scripts\test_release.ps1 -Version 0.1.0
```

## Fuentes online

La fuente recomendada es OpenMenu Cover API. No requiere cuenta de usuario y no expone credenciales privadas a la app de escritorio.

ScreenScraper directo queda como opcion avanzada para usuarios que quieran configurar sus propias credenciales. Otras fuentes estan reservadas para versiones futuras.

## Documentacion

- [Guia de usuario](docs/USER_GUIDE.es.md)
- [Preguntas frecuentes](docs/FAQ.es.md)
- [Seguridad](SECURITY.md)
- [Contribuir](CONTRIBUTING.md)

## Contacto

openmenu.gdemu.manager@gmail.com

## Licencia

OpenMenu GDEMU Manager se publica bajo GPL-3.0-or-later. Ver [LICENSE](LICENSE).
