# Preguntas frecuentes

## Incluye juegos o BIOS?

No. El proyecto no incluye ROMs, BIOS, respaldos de SD ni contenido con copyright.

## Puede borrar mi SD?

La app incluye diagnostico previo y bloquea escritura cuando la ruta no parece segura. Aun asi, es una beta: usa respaldos y revisa el diagnostico antes de aplicar cambios.

Durante el flujo normal, los juegos marcados para eliminar se mueven a una papelera interna de la SD, no se eliminan inmediatamente:

```text
_openmenu_gdemu_manager/trash/
```

## Que es la carpeta _openmenu_gdemu_manager?

Es una carpeta liviana creada por la app en la raiz de la SD. Guarda registro de respaldo, logs de operaciones y papelera interna de juegos eliminados.

No contiene juegos duplicados ni respaldos completos, salvo juegos que el usuario haya marcado para eliminar y que quedaron en la papelera interna.

## Por que la app compacta carpetas?

OpenMenu/GDEMU espera una estructura numerada. Si quedan huecos entre carpetas, la consola puede mostrar entradas vacias, sin titulo o sin caratula.

Al guardar cambios de juegos, la app deja los juegos activos compactados desde `02` hacia adelante.

## Por que reconstruye OpenMenu en vez de parchear track05.iso?

Porque el contenido del menu puede crecer. Parchear bytes dentro de `track05.iso` solo funciona si el nuevo bloque cabe exactamente en el espacio reservado. La app reconstruye la carpeta `01` para evitar depender de ese limite fragil.

## Que backup crea la app?

Hay dos niveles:

- backup completo de SD: opcional y recomendado antes de operaciones grandes;
- backup tecnico de `01`: automatico antes de reemplazar el menu OpenMenu.

## Por que Windows muestra una advertencia?

La beta no esta firmada digitalmente. Windows SmartScreen puede advertir que el archivo viene de internet o que el editor no es reconocido.

## Por que pesa cerca de 80 MB?

El ZIP incluye Python, PySide6/Qt y dependencias necesarias para correr sin instalar nada. Es normal para una app portable hecha en Python con interfaz Qt.

## Necesito instalar Python?

No si descargas el ZIP portable. Solo necesitas Python si quieres ejecutar o modificar el codigo fuente.

## Que significa modo portable?

Significa que la app guarda configuracion, logs, cache y archivos generados dentro de la carpeta `data/` junto al ejecutable, en vez de depender de una instalacion del sistema.

## Que significa calidad de caratula?

La calidad se calcula pensando en OpenMenu. El menu guarda caratulas normalizadas a 256x256, asi que una imagen de 512x512 o 1200x1200 no se guarda a ese tamano dentro de la SD: se reduce antes de entrar al menu.

Si una caratula ya viene desde los DAT de la SD, la app la muestra como fuente OpenMenu.

## Necesito cuenta de ScreenScraper?

No para el uso normal. La fuente recomendada es OpenMenu Cover API, que consulta caratulas sin pedir credenciales al usuario.

ScreenScraper directo existe como opcion avanzada para quienes quieran usar sus propias credenciales.

## Que pasa si la ruta queda bloqueada?

La app no permite continuar con acciones de escritura. Selecciona una SD GDEMU/OpenMenu valida, una carpeta vacia o un respaldo local limpio.

## La app formatea tarjetas SD?

No. La app no formatea, no repara sistemas de archivos y no ejecuta `chkdsk`.

## Como reporto un error?

Abre un issue en GitHub e incluye:

- version de la app;
- pasos para reproducir;
- captura de pantalla si ayuda;
- log si existe y no contiene datos sensibles.

No subas ROMs, BIOS, credenciales, respaldos de SD ni archivos privados.
