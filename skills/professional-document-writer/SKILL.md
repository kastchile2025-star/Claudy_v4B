---
name: professional-document-writer
description: Instrucciones y directrices para redactar informes, reportes y documentos académicos con un tono formal, estructura jerárquica clara y elementos enriquecedos como tablas y citas.
---

# Redacción y Estructura de Documentos Profesionales

Usa esta habilidad cuando el usuario te pida crear, generar, redactar o preparar un informe, reporte, documento formal, ensayo o entrega académica (archivos `.docx`).

## Directrices de Estructura

1. **Título Principal**: Comienza siempre el documento con un encabezado de nivel 1 (`# TÍTULO DEL DOCUMENTO`) centrado e impactante.
2. **Introducción o Resumen Ejecutivo**: El primer apartado debe ser siempre una introducción o resumen ejecutivo claro (máx. 1-2 párrafos) que plantee el objetivo.
3. **Jerarquía Clara**: 
   - Usa encabezados de nivel 2 (`## Sección`) para las partes principales.
   - Usa encabezados de nivel 3 (`### Subsección`) para detalles internos.
   - **Regla**: Nunca te saltes niveles (por ejemplo, de `#` a `###` directamente).
4. **Citas y Callouts**: Cuando menciones frases célebres, extractos de fuentes o notas de especial importancia, colócalas en formato de cita Markdown (`> Texto de la cita`).
5. **Datos y Comparaciones**: Toda información cuantitativa, comparativa o estructurada debe organizarse usando **tablas Markdown**.
6. **Conclusión / Recomendaciones**: Termina siempre con una sección formal de conclusiones o próximos pasos.
7. **Referencias Bibliográficas**: Incluye una sección final (`## Referencias` o `## Bibliografía`) con formato homogéneo de las fuentes consultadas.

## Directrices de Formato de Texto

- **Negritas inline**: Usa `**texto**` para destacar términos clave, métricas o conceptos críticos dentro de los párrafos.
- **Cursivas inline**: Usa `*texto*` para nombres de obras, términos extranjeros o énfasis secundario.
- **Listas**: Prefiere listas con viñetas (`- ` o `* `) para enumerar causas, consecuencias o características, en lugar de párrafos densos.

## Formato de Tablas Compatibles

Para asegurar que las tablas se rendericen de forma nativa y profesional en Word, dibújalas en formato Markdown estándar:

```markdown
| Columna A | Columna B | Columna C |
| --- | --- | --- |
| Dato 1A | Dato 1B | Dato 1C |
| Dato 2A | Dato 2B | Dato 2C |
```

- **Regla**: Todas las filas deben comenzar y terminar con el caracter pipe `|`.
- No añadas texto conversacional inmediatamente antes o después de la tabla; mantén una línea en blanco de separación.

## Anti-patrones a Evitar

- **NO** incluyas saludos ni comentarios introductorios en el cuerpo del documento generado (como *"Aquí tienes el informe que me pediste:"*). Escribe **únicamente** el texto del documento.
- **NO** dejes campos vacíos o placeholders como `[Insertar fecha aquí]`. Usa datos reales o la fecha de hoy.
- **NO** utilices títulos en negrita (`**Título**`) como si fuesen encabezados; usa los caracteres `#` correctos para que el parser genere estilos de Word adecuados.
