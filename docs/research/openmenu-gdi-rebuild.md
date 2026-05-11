# Investigación: reconstrucción de menú openMenu/GDEMU

## Resumen ejecutivo

El error "El bloque del menu excede el espacio disponible" no es un limite arbitrario: es la consecuencia directa de modificar `01/track05.iso` en sitio. La app localiza un bloque `[OPENMENU]` ya existente dentro de `track05.iso`, calcula el espacio disponible hasta una secuencia de bytes nulos y solo permite escribir si el nuevo contenido cabe exactamente dentro de ese hueco.

Ese enfoque solo es seguro para cambios pequenos. Cuando crece la lista de juegos, los metadatos o las caratulas, el menu debe reconstruirse como imagen GDI, no parchearse por bytes. La solucion tecnica recomendada es generar `OPENMENU.INI` y los datos del menu en un directorio temporal, reconstruir los tracks de la carpeta `01`, actualizar `disc.gdi` y reemplazar `01` de forma segura/atomica con backup.

## Hallazgos principales

- La app actual parchea `track05.iso` directamente. `patch_track05_menu()` busca `[OPENMENU]`, encuentra el final con `b"\x00" * 64`, calcula `original_span` y falla si `len(block) > original_span`.
- La validacion se ejecuta antes de aplicar cambios destructivos: `SaveChangesWorker.run()` llama a `validate_track05_menu_capacity()` antes de eliminar/copiar juegos, y luego vuelve a llamar a `patch_track05_menu()`.
- El parche de caratulas tambien escribe dentro de `track05.iso` con offsets fijos: `IMG_START + cover_index * IMG_SIZE`.
- En la SD real inspeccionada (`H:\01`), `disc.gdi` declara 5 tracks y `track05.iso` como track 5, sector 2048, LBA `487774`. El bloque `[OPENMENU]` estaba en offset `118833152`, alineado a sector 2048, con span disponible de `12610` bytes hasta los nulos.
- La plantilla de `GDMENUCardManager` para openMenu tambien usa 5 tracks, pero con LBA distinto para `track05.iso` (`544180`). Esto confirma que los LBA no son constantes universales: dependen del layout generado.
- `GDMENUCardManager` no parchea el bloque del menu en sitio. Genera `OPENMENU.INI` en `lowdensity_data` y `data`, copia `menu_gdi`/`menu_data`, invoca `DiscUtils.Gdrom.GDromBuilder`, genera `track01.iso`, reconstruye la zona de alta densidad y actualiza `disc.gdi`.
- `openMenu` lee la lista desde `OPENMENU.INI`; el codigo fuente llama a `list_read(PATH_PREFIX "OPENMENU.INI")`.
- `openMenu` usa DATs para arte y metadata: `BOX.DAT`, `ICON.DAT`, `BOX_EX.DAT`, `ICON_EX.DAT` y `META.DAT` aparecen en el codigo y documentacion de openMenu/OpenMenu Virtual Folder Bundle.
- El proyecto local es GPL-3.0-or-later. `GDMENUCardManager` y el bundle de Derek Pascarella usan GPL-3.0; `openMenu` indica BSD 3-clause; `DiscUtilsGD` incluye licencia MIT/DiscUtils. Se puede tomar inspiracion de todos, pero copiar codigo exige revisar compatibilidad y avisos.

## Estructura de la SD

Una SD GDEMU/openMenu esperada tiene una raiz FAT32 con carpetas numeradas. La carpeta `01` contiene el menu de arranque. Las carpetas `02` en adelante contienen juegos o discos: normalmente `disc.gdi` mas tracks (`track01.bin`, `track02.raw`, `track03.bin`, etc.) o `disc.cdi`; la app ademas escribe `name.txt` para compatibilidad con otros managers.

La app local detecta esta estructura en `scan_sd_root()`, ignora `01`, recorre carpetas numericas, lee `name.txt`, detecta `disc.gdi`/`disc.cdi`, y combina metadata de `OPENMENU.current.generated.ini` y del bloque `[OPENMENU]` embebido en `01/track05.iso`.

## Estructura de la carpeta 01

La carpeta `01` representa el disco del menu en formato GDI. En las muestras revisadas contiene:

- `disc.gdi`: descriptor de tracks, LBA, tipo y tamano de sector.
- `track01.iso`: track de baja densidad generado con archivos pequenos de menu.
- `track02.raw`: audio/raw dummy.
- `track03.iso`: inicio de la zona de alta densidad; contiene IP.BIN/bootsector y estructura ISO9660/directorios.
- `track04.raw`: audio/raw dummy.
- `track05.iso`: track final de datos de alta densidad; contiene datos grandes del menu, DATs, caratulas, metadata y el bloque/lista usado por openMenu en el layout generado.

Ejemplo real inspeccionado en `H:\01\disc.gdi`:

```text
5
1 0 4 2048 track01.iso 0
2 450 0 2352 track02.raw 0
3 45000 4 2048 track03.iso 0
4 487623 0 2352 track04.raw 0
5 487774 4 2048 track05.iso 0
```

Ejemplo de plantilla de `GDMENUCardManager` para openMenu:

```text
5
1 0 4 2048 track01.iso 0
2 450 0 2352 track02.raw 0
3 45000 4 2048 track03.iso 0
4 60000 0 2352 track04.raw 0
5 544180 4 2048 track05.iso 0
```

La diferencia entre LBAs muestra por que no es correcto asumir offsets fijos salvo dentro de una imagen ya generada y solo mientras su layout no cambie.

## Rol de track05.iso

`track05.iso` es el ultimo track de datos del menu GDI cuando hay tracks de audio/dummy entre la cabecera y los datos finales. En las imagenes revisadas contiene datos de openMenu que pueden incluir `BOX.DAT`, `ICON.DAT`, `META.DAT`, texturas y el contenido de `OPENMENU.INI` embebido en el track final.

El parche actual falla porque trata una parte de ese track como un bloque de texto de tamano fijo. Si el nuevo `OPENMENU.INI` es menor o igual que el espacio original, se escribe y se rellena con nulos. Si es mayor, la app no puede desplazar el resto de los datos porque eso invalidaria offsets internos, ubicaciones ISO9660, separacion de tracks, LBA del ultimo track y posiblemente el TOC escrito en IP.BIN.

Cambiar el tamano de `track05.iso` no es suficiente por si solo. Tambien se debe actualizar `disc.gdi`; si cambian las posiciones de archivos dentro de la imagen, se deben regenerar las tablas ISO9660; y si el layout de tracks cambia, se debe recalcular la informacion de tracks/TOC que `GDromBuilder` escribe en el bootsector.

## Flujo actual de nuestra app

1. `diagnose_storage()` valida ruta, FAT32/unidad, estructura numerica y compatibilidad de menu. Para openMenu compatible exige detectar `[OPENMENU]` en `01/track05.iso`.
2. `scan_sd_root()` carga metadata desde `OPENMENU.current.generated.ini`, desde `root/OPENMENU.current.generated.ini` si existe y desde `parse_openmenu_from_track(root / "01" / "track05.iso")`.
3. El usuario edita juegos, nombres, metadata y caratulas en memoria.
4. `SaveChangesWorker.run()` construye listas de eliminaciones, adiciones y juegos conservados.
5. Antes de modificar la SD, llama a `validate_track05_menu_capacity(self.root_path / "01" / "track05.iso", kept)`.
6. Elimina carpetas marcadas usando la papelera.
7. Copia juegos nuevos a carpetas numeradas y escribe `name.txt`.
8. Reescribe `name.txt` para juegos existentes.
9. Genera `OPENMENU.current.generated.ini` en el area local de datos de la app con `write_openmenu_ini(kept)`.
10. Parchea el bloque `[OPENMENU]` dentro de `01/track05.iso` con `patch_track05_menu()`.
11. Parchea caratulas dentro de `01/track05.iso` con `patch_track05_cover()` en offsets fijos.
12. Actualiza `_cover_manager_state.json`.

## Punto exacto de fallo

El limite de bloque esta en `src/openmenu_gdemu_manager/dreamcast/sd_writer.py`:

```python
def _track05_menu_block(track_path: Path, games: list[GameItem]) -> tuple[bytes, int, int]:
    data = track_path.read_bytes()
    start = data.find(b"[OPENMENU]")
    if start == -1:
        raise ValueError("No se encontro bloque [OPENMENU] en track05.iso")
    end = data.find(b"\x00" * 64, start)
    if end == -1:
        raise ValueError("No se encontro el final del bloque del menu en track05.iso")
    original_span = end - start
    block = build_openmenu_text(games, newline="\n").encode("latin-1", errors="replace")
    return block, start, original_span
```

`validate_track05_menu_capacity()` y `patch_track05_menu()` fallan con `_menu_capacity_error()` cuando `len(block) > original_span`:

```python
"El bloque del menu excede el espacio disponible "
f"({used / 1024:.1f} KB usados > {available / 1024:.1f} KB disponibles; "
f"faltan {over / 1024:.1f} KB). "
f"Detalle tecnico: {used} > {available} bytes."
```

Esto prueba que el diseno actual reemplaza bytes dentro del ISO sin reconstruir la imagen.

## Estrategias posibles

### 1. Parchear en sitio

Ventajas:

- Es simple y rapido.
- No requiere dependencias nuevas.
- Funciona cuando el nuevo bloque `[OPENMENU]` es menor o igual al span original.

Riesgos:

- Falla al crecer el INI.
- No puede insertar archivos nuevos ni redimensionar DATs.
- Parchear caratulas por offsets fijos depende de que el layout de `BOX.DAT`/imagenes no cambie.
- No corrige `disc.gdi`, ISO9660 ni TOC.

Complejidad: baja, pero no resuelve el problema.

### 2. Reconstruir solo track05.iso

Ventajas:

- Reduce el alcance del reemplazo.
- Podria preservar tracks 1 a 4.

Riesgos:

- `track05.iso` forma parte de una imagen GDI multi-track; no es una unidad aislada segura.
- Si cambia el tamano, `disc.gdi` debe actualizarse.
- Si el contenido depende de tablas ISO9660 generadas en `track03.iso`, reconstruir solo el ultimo track puede dejar referencias incoherentes.
- No garantiza que IP.BIN/TOC y ubicacion del ejecutable principal sigan correctos.

Complejidad: media/alta, con riesgo tecnico alto.

### 3. Reconstruir toda la carpeta 01

Ventajas:

- Es el flujo usado por GDMENUCardManager.
- Recalcula `track03.iso`, `track05.iso`, LBA y `disc.gdi` de forma consistente.
- Permite que `OPENMENU.INI`, `BOX.DAT`, `ICON.DAT`, `META.DAT`, temas y otros datos crezcan dentro de los limites reales del GD-ROM.
- Facilita staging, validacion y rollback.

Riesgos:

- Requiere plantilla correcta de `menu_gdi`, `menu_data`, `IP.BIN` y `1ST_READ.BIN`.
- Requiere herramienta o libreria de reconstruccion fiable.
- Reemplazar `01` debe hacerse con backup y validacion para no dejar la SD sin menu.

Complejidad: media/alta, pero es la solucion robusta.

### 4. Usar herramienta externa

Ventajas:

- `buildgdi`/`GDromBuilder` ya resuelve ISO9660, LBA offset, CDDA/dummy tracks, ultimo track y `disc.gdi`.
- Menor probabilidad de introducir bugs de formato GDI.
- Permite una prueba experimental rapida.

Riesgos:

- Dependencia externa .NET o binario empaquetado.
- Hay que gestionar distribucion, version, rutas y errores de proceso.
- Licencias y avisos deben revisarse antes de redistribuir binarios o codigo.

Complejidad: media.

### 5. Usar librería interna

Ventajas:

- Mejor integracion con la app Python.
- Sin proceso externo en tiempo de ejecucion.
- Permite validaciones y progreso mas controlados.

Riesgos:

- Portar ISO9660/GDI correctamente es delicado.
- Debe replicar detalles de `DiscUtilsGD`: LBA offset 45000, end sector 549150, colocacion del boot bin al final, separacion de 150 sectores alrededor de CDDA y escritura de `disc.gdi`.
- Mayor superficie de bugs antes de tener fixtures de validacion.

Complejidad: alta.

## Recomendación técnica

No corregir el error aumentando `original_span` ni relajando `_menu_capacity_error()`. La app debe dejar de usar el parcheo de `track05.iso` como camino principal de guardado.

La implementacion futura recomendada es:

1. Generar `OPENMENU.INI` desde los `GameItem` actuales.
2. Preparar un staging temporal con:
   - `menu_gdi` base para openMenu.
   - `menu_low_data` si existe.
   - `menu_data` con `1ST_READ.BIN`, fuentes, temas, DATs y assets.
   - `OPENMENU.INI` tanto en baja densidad como en alta densidad.
3. Reconstruir la carpeta `01` completa con `GDromBuilder` o una herramienta equivalente.
4. Validar que el staging contiene `disc.gdi`, `track01.iso`, `track02.raw`, `track03.iso`, `track04.raw` y `track05.iso`.
5. Reemplazar `root/01` mediante una operacion segura con backup.

Para una primera version, conviene usar una herramienta externa basada en `GDIbuilder`/`DiscUtilsGD` o integrar `DiscUtilsGD` respetando licencias. Portar la logica a Python solo deberia considerarse despues de tener fixtures binarios y pruebas de reconstruccion confiables.

Los archivos minimos que debe generar o ensamblar la app para openMenu son:

- `OPENMENU.INI` con entrada `01` para openMenu y entradas `02..N` para juegos.
- `disc.gdi` actualizado.
- Tracks de la carpeta `01` generados de forma consistente.
- `1ST_READ.BIN` y assets base de openMenu desde plantilla.
- `BOX.DAT`/`ICON.DAT` para caratulas cuando se gestionen desde la app.
- `META.DAT` si se incluye metadata extendida.
- `name.txt` en carpetas de juegos para compatibilidad externa.

## Plan de implementación futuro

### 1. Prueba experimental

- Crear un script experimental fuera del flujo de la app, por ejemplo `scripts/experiments/rebuild_openmenu_slot01.py`.
- Usar una copia local de una SD, nunca la SD real.
- Tomar una carpeta `01` base, extraer/armar `menu_data`, generar `OPENMENU.INI`, ejecutar `buildgdi`/`GDromBuilder` y comparar `disc.gdi`/tracks resultantes.
- Registrar si `openMenu` lee correctamente el nuevo `OPENMENU.INI` y si el tamano ya no depende del span anterior.

### 2. Generador de OPENMENU.INI

- Reusar `build_openmenu_text()` como fuente unica.
- Ajustar campos faltantes de openMenu moderno: `folder`, `type` y carpetas alternativas solo si se decide soportarlas.
- Definir encoding y fallback: mantener ASCII/Latin-1 compatible para el contenido que openMenu pueda leer.

### 3. Reconstrucción de imagen

- Introducir un servicio nuevo, por ejemplo `openmenu_rebuilder`, que reciba `root`, `games`, plantilla y rutas de DATs.
- El servicio debe construir staging completo y devolver una carpeta `01` candidata.
- No debe modificar `root/01` durante la generacion.
- La herramienta debe actualizar `disc.gdi` despues de generar tracks.

### 4. Reemplazo seguro de carpeta 01

- Crear `01.new.<timestamp>` en la misma unidad.
- Validar staging antes del swap.
- Renombrar `01` a `01.backup.<timestamp>`.
- Renombrar `01.new.<timestamp>` a `01`.
- Si falla el rename final, intentar restaurar backup.
- No borrar backup automaticamente en la primera version.

### 5. Validaciones

- Verificar `disc.gdi` parseable y cantidad de tracks coherente.
- Verificar que cada track listado existe y tiene tamano mayor que cero.
- Verificar que los LBA estan en orden y que `track03` empieza en LBA 45000.
- Verificar que `OPENMENU.INI` generado existe dentro del contenido que se empaqueta.
- Verificar espacio libre antes de staging y antes del swap.

### 6. Tests

- Unit tests para `OPENMENU.INI`: `num_items`, entrada `01`, orden por slot, nombres largos, campos vacios y caracteres no soportados.
- Tests del flujo de guardado futuro para confirmar que no llama a `_track05_menu_block()` cuando se reconstruye menu.
- Tests de `disc.gdi` sobre fixtures generados: cantidad de tracks, LBA, sector size y nombres.
- Tests de atomicidad: fallo durante build no toca `01`; fallo durante reemplazo conserva backup.
- Tests de compatibilidad: SD con openMenu antiguo, gdMenu basico y carpeta `01` faltante siguen bloqueadas o migradas segun diagnostico.

## Riesgos

- Corrupcion de SD: reemplazar `01` sin staging/backup puede dejar la consola sin menu. La implementacion debe generar primero, validar despues y reemplazar al final.
- Licencias: el proyecto local es GPL-3.0-or-later; `GDMENUCardManager` es GPL-3.0; `DiscUtilsGD` incluye licencia MIT/DiscUtils; `openMenu` indica BSD 3-clause. Copiar codigo requiere conservar licencias y avisos; invocar herramientas externas tambien requiere documentar redistribucion.
- Compatibilidad openMenu: existen forks y variantes. Algunos usan `LIST.INI` para gdMenu, otros `OPENMENU.INI` para openMenu; los DATs pueden variar entre builds.
- Compatibilidad GDEMU/clones: tiempos de deteccion, orden de carpetas y formato FAT32 importan. La app ya tiene diagnostico, pero el rebuilder debe ser conservador.
- Datos de caratulas: pasar de offsets fijos a DATs requiere mapear serial/product ID correctamente. El bundle de Derek Pascarella documenta traducciones de serial para que `BOX.DAT`/`ICON.DAT` coincidan con lo que openMenu espera.
- Tamano GD-ROM: reconstruir puede fallar si `menu_data` crece demasiado. El error correcto en ese caso es "imagen demasiado grande para GD-ROM", no un error de bloque.

## Referencias

### Código local revisado

- `src/openmenu_gdemu_manager/dreamcast/sd_writer.py`: `build_openmenu_text()`, `write_openmenu_ini()`, `patch_track05_menu()`, `validate_track05_menu_capacity()`, `_track05_menu_block()`, `_menu_capacity_error()`, `patch_track05_cover()`.
- `src/openmenu_gdemu_manager/ui/workers.py`: `SaveChangesWorker.run()`, especialmente validacion de capacidad, escritura de `OPENMENU.current.generated.ini`, parche de menu y parche de caratulas.
- `src/openmenu_gdemu_manager/dreamcast/scanner.py`: `scan_sd_root()` y `_load_menu_metadata()` leen metadata desde INI local y desde `01/track05.iso`.
- `src/openmenu_gdemu_manager/dreamcast/metadata.py`: `parse_openmenu_from_track()` tambien busca `[OPENMENU]` y termina en 64 nulos.
- `src/openmenu_gdemu_manager/dreamcast/pvr.py`: extraccion de caratulas desde offsets fijos `IMG_START + index * IMG_SIZE`.
- `src/openmenu_gdemu_manager/services/setup_service.py`: `install_openmenu_base()` actualmente copia una plantilla `01` completa a SD vacia.
- `tests/test_sd_writer.py`: prueba que la validacion de capacidad falla antes de escribir cuando el bloque nuevo no cabe.

### Repositorios y documentación externa

- GDMENUCardManager: https://github.com/sonik-br/GDMENUCardManager
- GDMENUCardManager README: https://github.com/sonik-br/GDMENUCardManager/blob/master/README.md
- openMenu Virtual Folder Bundle: https://github.com/DerekPascarella/openMenu-Virtual-Folder-Bundle
- openMenu Virtual Folder Bundle README: https://github.com/DerekPascarella/openMenu-Virtual-Folder-Bundle/blob/main/README.MD
- GDIbuilder: https://github.com/Sappharad/GDIbuilder
- GDIbuilder README: https://raw.githubusercontent.com/Sappharad/GDIbuilder/master/README.md
- GDromBuilder: https://github.com/Sappharad/GDIbuilder/blob/master/DiscUtilsGD/DiscUtils.Iso9660/GDROM/GDromBuilder.cs
- DiscUtilsGD NuGet/project metadata: `DiscUtilsGD.csproj` en GDIbuilder.
- openMenu `gd_list.c`: `list_read_default()` lee `OPENMENU.INI`.
- openMenu `db_list.c`: carga `META.DAT`.
- openMenu `txr_manager.c`: carga `ICON.DAT`, `BOX.DAT`, `ICON_EX.DAT` y `BOX_EX.DAT`.

### Fragmentos relevantes de código local

```python
validate_track05_menu_capacity(self.root_path / "01" / "track05.iso", kept)
...
write_openmenu_ini(kept)
patch_track05_menu(self.root_path / "01" / "track05.iso", kept)
...
patch_track05_cover(self.root_path / "01" / "track05.iso", int(game.cover_index), image_path)
```

```python
start = data.find(b"[OPENMENU]")
end = data.find(b"\x00" * 64, start)
original_span = end - start
block = build_openmenu_text(games, newline="\n").encode("latin-1", errors="replace")
```

Estos fragmentos son la evidencia principal de que el fallo no se debe corregir ampliando un limite, sino reemplazando el modelo de guardado por reconstruccion de menu.
