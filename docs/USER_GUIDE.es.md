# Guia de usuario

## 1. Descargar y abrir

Descarga el ZIP portable desde GitHub Releases, extraelo completo en una carpeta nueva y ejecuta `OpenMenuGDEMUManager.exe`.

No necesitas instalar Python. La aplicacion es portable y guarda sus datos en la carpeta `data/` junto al ejecutable.

## 2. Seleccionar una ruta

Puedes seleccionar:

- una tarjeta SD preparada para GDEMU/OpenMenu;
- una carpeta local de respaldo;
- una carpeta vacia donde preparar contenido.

El asistente revisa la ruta antes de permitir lectura o escritura.

## 3. Entender el diagnostico

El asistente muestra tarjetas de estado:

- **Estado de unidad**: indica si la ruta parece accesible.
- **Sistema de archivos**: valida FAT32 cuando corresponde a una SD.
- **Estructura GDEMU**: detecta carpetas numericas y estructura OpenMenu.
- **Contenido no GDEMU**: advierte si hay archivos que no parecen parte de una SD GDEMU.

Si la ruta queda bloqueada, la app no habilita acciones de escritura. Esto protege carpetas personales, discos internos y rutas que no parecen una SD GDEMU/OpenMenu.

La carpeta interna `_openmenu_gdemu_manager/` pertenece a la app y se ignora en el diagnostico normal.

## 4. Administrar caratulas

La app puede buscar caratulas desde:

- carpetas locales configuradas;
- openMenu image DB;
- Libretro thumbnails;
- OpenMenu Cover API.

La fuente OpenMenu Cover API no requiere que el usuario configure credenciales.

Cuando escaneas una SD que ya tiene OpenMenu funcionando, la app intenta leer las caratulas reales desde los archivos DAT del menu. Esas caratulas se extraen a cache local solo para mostrarlas en la interfaz, pero la fuente de verdad sigue siendo la SD.

OpenMenu usa caratulas normalizadas a 256x256. Por eso una imagen original grande se guarda reducida antes de entrar al menu. En la tabla, la calidad indica la utilidad para OpenMenu, no el tamano original maximo de internet.

## 5. Agregar juegos

Usa el boton **Agregar** para seleccionar juegos GDI/CDI o carpetas con juegos.

La app asigna el siguiente slot disponible y marca el juego como pendiente. Nada se copia a la SD hasta presionar **Guardar cambios**.

Cuando se guarda, la app copia el juego, lee el Product ID real cuando es posible, actualiza `name.txt`, reconstruye OpenMenu y registra la operacion.

## 6. Quitar juegos

Puedes marcar un juego para eliminar desde la fila o seleccionar varios juegos y usar la accion masiva de eliminar.

Los juegos no se borran en ese momento. Al presionar **Guardar cambios**, se mueven a la papelera interna:

```text
_openmenu_gdemu_manager/trash/
```

Despues de eliminar juegos, la app compacta las carpetas para evitar huecos. Esto es importante porque OpenMenu puede mostrar entradas vacias si existen indices sin su carpeta correspondiente.

## 7. Aplicar cambios

Antes de aplicar cambios:

- revisa el diagnostico;
- confirma que estas trabajando sobre la SD o respaldo correcto;
- manten un respaldo reciente.

La app no formatea unidades y no ejecuta reparaciones de disco. Solo modifica archivos relacionados con la administracion OpenMenu/GDEMU cuando la ruta esta permitida.

Durante el guardado, la app puede:

- copiar juegos nuevos;
- mover juegos eliminados a la papelera interna;
- compactar carpetas numericas;
- guardar caratulas;
- reconstruir la carpeta `01` de OpenMenu;
- crear un backup tecnico automatico de `01`;
- escribir un log en `_openmenu_gdemu_manager/transactions.jsonl`.

No desconectes la SD ni apagues el PC mientras se aplican cambios.

## 8. Reparaciones sugeridas al escanear

Si la app detecta diferencias entre el menu OpenMenu y las carpetas fisicas, mostrara una alerta. Ejemplos:

- faltan carpetas esperadas;
- hay carpetas sin entrada en OpenMenu;
- hay huecos que requieren compactacion;
- el Product ID del menu no coincide con el disco real.

La opcion **Guardar y reparar ahora** reconstruye el menu y corrige la estructura cuando es posible.

## 9. Actualizar

Al iniciar, la app revisa GitHub Releases. Si hay una version nueva, muestra un aviso y abre la pagina de descarga.

La app no se reemplaza a si misma. Para actualizar, descarga el nuevo ZIP y copia o conserva la carpeta `data/` si quieres mantener configuracion y cache.
