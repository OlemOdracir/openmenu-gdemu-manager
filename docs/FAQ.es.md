# Preguntas frecuentes

## ¿Incluye juegos o BIOS?

No. El proyecto no incluye ROMs, BIOS, respaldos de SD ni contenido con copyright.

## ¿Puede borrar mi SD?

La app incluye diagnostico previo y bloquea escritura cuando la ruta no parece segura. Aun asi, es una beta: usa respaldos y revisa el diagnostico antes de aplicar cambios.

## ¿Por que Windows muestra una advertencia?

La beta no esta firmada digitalmente. Windows SmartScreen puede advertir que el archivo viene de internet o que el editor no es reconocido.

## ¿Por que pesa cerca de 80 MB?

El ZIP incluye Python, PySide6/Qt y dependencias necesarias para correr sin instalar nada. Es normal para una app portable hecha en Python con interfaz Qt.

## ¿Necesito instalar Python?

No si descargas el ZIP portable. Solo necesitas Python si quieres ejecutar o modificar el codigo fuente.

## ¿Que significa modo portable?

Significa que la app guarda configuracion, logs, cache y archivos generados dentro de la carpeta `data/` junto al ejecutable, en vez de depender de una instalacion del sistema.

## ¿Necesito cuenta de ScreenScraper?

No para el uso normal. La fuente recomendada es OpenMenu Cover API, que consulta caratulas sin pedir credenciales al usuario.

ScreenScraper directo existe como opcion avanzada para quienes quieran usar sus propias credenciales.

## ¿Que pasa si la ruta queda bloqueada?

La app no permite continuar con acciones de escritura. Selecciona una SD GDEMU/OpenMenu valida, una carpeta vacia o un respaldo local limpio.

## ¿La app formatea tarjetas SD?

No. La app no formatea, no repara sistemas de archivos y no ejecuta `chkdsk`.

## ¿Como reporto un error?

Abre un issue en GitHub e incluye:

- version de la app;
- pasos para reproducir;
- captura de pantalla si ayuda;
- log si existe y no contiene datos sensibles.

No subas ROMs, BIOS, credenciales, respaldos de SD ni archivos privados.
