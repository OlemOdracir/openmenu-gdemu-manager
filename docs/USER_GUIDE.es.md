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

## 4. Administrar caratulas

La app puede buscar caratulas desde:

- carpetas locales configuradas;
- openMenu image DB;
- Libretro thumbnails;
- OpenMenu Cover API.

La fuente OpenMenu Cover API no requiere que el usuario configure credenciales.

## 5. Aplicar cambios

Antes de aplicar cambios:

- revisa el diagnostico;
- confirma que estas trabajando sobre la SD o respaldo correcto;
- mantén un respaldo reciente.

La app no formatea unidades y no ejecuta reparaciones de disco. Solo modifica archivos relacionados con la administracion OpenMenu/GDEMU cuando la ruta esta permitida.

## 6. Actualizar

Al iniciar, la app revisa GitHub Releases. Si hay una version nueva, muestra un aviso y abre la pagina de descarga.

La app no se reemplaza a si misma. Para actualizar, descarga el nuevo ZIP y copia o conserva la carpeta `data/` si quieres mantener configuracion y cache.
