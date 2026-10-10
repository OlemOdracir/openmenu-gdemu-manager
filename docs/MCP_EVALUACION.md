# Evaluación de CLI y MCP para OpenMenu

Fecha: 9 de octubre de 2026. Alcance: incorporar control para agentes sin alterar
la aplicación PySide6 ni duplicar las reglas de importación y transacciones.

## Decisión propuesta

MCP es viable y útil para diagnóstico y administración asistida. Recomiendo un
adaptador local opcional sobre servicios Python compartidos, con transporte
stdio y SDK oficial; la interfaz gráfica continúa como cliente de esos servicios.
No exige HTML, un navegador embebido, Tailwind ni reemplazar Qt.

Esta fase implementa la base comprobable: consultas Python sin GUI y CLI JSON
para validar imágenes y diagnosticar destinos explícitos. **No implementa ni
activa aún un servidor MCP**, un puerto HTTP o acciones de escritura para agentes.
La evaluación no agrega una dependencia del SDK al portable de escritorio.

## Opciones

| Opción | Ventajas | Costes y límites | Recomendación |
| --- | --- | --- | --- |
| CLI JSON | Reproducible desde terminal y CI; ninguna dependencia nueva; útil hoy para agentes capaces de ejecutar comandos. | El agente debe conocer comandos/códigos; no ofrece descubrimiento MCP. | Base implementada. |
| MCP local stdio | El cliente descubre herramientas/esquemas; procesos locales; integración con distintos agentes. | SDK/dependencias opcionales, control de rutas, protocolo y pruebas cliente-servidor. | Próximo adaptador recomendado. |
| MCP/HTTP | Permite clientes remotos y procesos persistentes. | Autenticación, origen, exposición de rutas, TLS según despliegue, concurrencia y ciclo de sesión. | Sin necesidad actual; diferir. |
| Automatizar botones Qt | Reproduce algunas acciones humanas. | Depende de foco, resolución y estado; falla al esconder errores o bloquear workers. | Útil para QA visual; no como API de negocio. |

## Lo implementado

`services/agent_queries.py` contiene operaciones de solo lectura, sin iniciar
QApplication, migración de datos, proveedores remotos ni transacciones.
`cli.py` es otro cliente de esos servicios. Cada petición exige una ruta; no
busca SD físicas automáticamente. Los resultados tienen schema_version=1,
read_only=true y hardware_verified=false. Los mensajes pueden ser EN/ES;
los identificadores y categorías de máquina no cambian con el idioma.

```powershell
python -m openmenu_gdemu_manager.cli --language es validate-image "ruta/al/disc.cdi"
python -m openmenu_gdemu_manager.cli --language es diagnose-storage "ruta/al/destino"
```

Después de instalar el proyecto, `openmenu-gdemu-agent` ofrece los mismos comandos.
Siempre imprime un documento JSON en stdout. validate-image retorna 0 cuando
los controles soportados pasan, 2 ante fallo estructural, 3 ante formato no
soportado y 4 ante lectura fallida. argparse también retorna 2 por uso incorrecto
(en stderr, sin resultado JSON). diagnose-storage retorna 0 cuando produjo el
diagnóstico; **eso no significa que el destino esté autorizado para escribir**.
El consumidor debe leer sus estados. Un diagnóstico es una fotografía, no un
permiso persistente. Ninguno de los comandos escribe en el destino.

## Contrato del futuro adaptador MCP

| Herramienta | Entrada | Resultado | Estado |
| --- | --- | --- | --- |
| validate_image | Ruta dentro de las raíces autorizadas al iniciar el servidor. | Categoría, código, pistas/límites CDI, alcance y limitaciones. | Servicio/CLI disponibles; adaptador propuesto. |
| diagnose_destination | Destino dentro de las raíces autorizadas. | Almacenamiento, menú, configuración GDEMU.ini, permisos diagnosticados. | Servicio/CLI disponibles; adaptador propuesto. |
| list_games | Destino, filtro, paginación y límite. | Identidad, región y estado de carátula; sin bytes de ROM. | Propuesto. |
| find_cover_candidates | Juego, consulta temporal, límite y proveedor habilitado. | Alternativas con región/tamaño/fuente; sin guardar la elección. | Propuesto, acceso a red declarado. |
| prepare_changes / review_plan | Cambios explícitos de nombre/carátula/importación. | Plan y estado pendientes; búsqueda temporal separada del nombre guardado. | Requiere una capa de sesión/aplicación compartida. |
| apply_plan / recover_operation | Plan exacto vigente y autorización explícita. | Trabajo, progreso, resultado o recuperación. | Diferir hasta las condiciones de escritura descritas abajo. |

Las consultas locales usarían readOnlyHint=true y openWorldHint=false; búsqueda
remota declararía openWorldHint=true. Las anotaciones son información del
protocolo, **no un mecanismo de autorización**. No basta etiquetar una herramienta
como segura. El SDK debe validar esquemas y el servidor aplicar los límites.

## Condiciones antes de activar MCP

1. Raíces de lectura explícitas en la configuración de arranque. Resolver rutas
   y comprobar contención antes de leer; rechazar escapes por rutas relativas,
   enlaces/junctions y cambios de objetivo. No exponer lectura arbitraria del PC.
2. SDK oficial como extra opcional con versión probada y licencia registrada.
   Mantener la GUI sin esa dependencia obligatoria. No fabricar JSON-RPC propio.
3. stdio reservado al protocolo; registros solo stderr o archivos privados.
   Límites de llamadas/resultados y cancelación; paginar listas y candidatos.
4. Esquemas estables y errores de herramienta diferenciados de errores de
   protocolo. Datos de nombres, imágenes y archivos se tratan como datos, nunca
   instrucciones. No enviar ROMs, credenciales ni inventarios sin necesidad.
5. Probar initialize, tools/list y tools/call con un cliente MCP real, además de
   las funciones internas. Comprobar rutas, entradas inválidas, cierre y errores.
6. Auditoría independiente de esa integración antes de anunciar MCP disponible.

Antes de permitir escrituras: plan revisable con identidad/huella y caducidad,
autorización para ese destino y contenido, exclusión mutua entre GUI/CLI/MCP,
revalidación de almacenamiento y fuente inmediatamente antes de aplicar,
transacciones originales y recuperación. Un resultado write_allowed anterior
no autoriza una petición posterior. No ejecutar escrituras conectando un agente
a botones ni directamente a SdSlotTransactionService sin esas precondiciones.

La GUI tiene actualmente estado de sesión en MainWindowV2/ProductionWorkspace y
workers Qt. El adaptador de consulta ya puede compartir funciones puras; las
mutaciones requieren extraer la coordinación de sesión y trabajos a una capa de
aplicación. Eso evita dos implementaciones que diverjan y mantiene la confirmación
humana disponible en el cliente que corresponda.

## Fuentes primarias consultadas

- [MCP Python SDK oficial](https://py.sdk.modelcontextprotocol.io/): servidores,
  herramientas y transporte del SDK. Seleccionar/pinar su versión al implementar.
- [Transportes MCP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports):
  stdio y Streamable HTTP, separación de stdout/stderr.
- [Herramientas MCP](https://modelcontextprotocol.io/specification/2025-11-25/server/tools):
  esquemas, resultados estructurados, errores y controles de acceso.

La CLI se prueba con destinos sintéticos y sin GUI. Los requisitos del servidor
son propuesta de arquitectura; no cuentan como pruebas realizadas de MCP.
