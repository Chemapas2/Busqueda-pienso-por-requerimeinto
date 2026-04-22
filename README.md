# FEDNA Feed Recommender

Aplicación Streamlit para trabajar con un Excel de formulación y analizar piensos de dos maneras distintas:

1. **Análisis de búsqueda y ranking**
2. **Comparativa directa de piensos**

La app usa el **Excel cargado** como fuente de datos para calcular resultados. Los PDFs FEDNA, cuando existen, se usan como **apoyo técnico informativo** dentro del chat, pero no deciden el ranking.

---

## 1. Análisis de búsqueda y ranking

Este modo sirve para partir de una necesidad técnica escrita en lenguaje natural y obtener los piensos del Excel que mejor encajan.

### Flujo de uso

- Seleccionar la **especie/categoría**.
- Cargar el **Excel**.
- Elegir los **nutrientes** que quieres mostrar o usar como referencia visual.
- Escribir una consulta en el cuadro de texto, por ejemplo:
  - `busca gestación con lisina > 0.70 y precio < 290`
  - `prioriza proteína alta y precio bajo`
  - `sin trigo y con calcio entre 0.80 y 1.10`
- Pulsar **Buscar y rankear**.

### Qué hace la app

- Interpreta la consulta.
- Aplica filtros sobre el Excel por nutrientes, precio, ingredientes o texto.
- Ordena los productos por una **aptitud** relativa.
- Devuelve el **Top N** de recomendaciones.

### Qué devuelve

- Tabla de ranking con:
  - pienso
  - precio
  - aptitud
  - nutrientes visibles
- Explicación resumida del porqué del ranking.
- Detalle del pienso seleccionado.
- Informe resumen.
- Exportación a **Excel** del análisis.

### Cuándo usarlo

- Cuando quieres encontrar productos compatibles con una necesidad técnica.
- Cuando partes de criterios nutricionales, económicos o de fórmula.
- Cuando necesitas cribar rápidamente muchos piensos del Excel.

---

## 2. Comparativa directa de piensos

Este modo sirve para comparar varios productos concretos entre sí, sin pedir primero un ranking por consulta.

### Flujo de uso

- En la sección **Comparativa directa de piensos**, seleccionar uno o varios productos de la base de datos.
- La app genera la comparación con los nutrientes seleccionados y con la fórmula disponible.

### Qué devuelve

- Tabla comparativa de:
  - precio
  - nutrientes seleccionados
- Tabla comparativa de ingredientes:
  - ingredientes presentes
  - porcentaje de inclusión
- Exportación a **Excel** de la comparativa.

### Cuándo usarlo

- Cuando ya sabes qué piensos quieres revisar.
- Cuando quieres ver diferencias rápidas entre fórmulas.
- Cuando quieres comparar finalistas después del ranking.

---

## Diferencia entre ambos análisis

### Búsqueda y ranking
Parte de una **pregunta o criterio técnico** y devuelve los productos del Excel que mejor encajan.

### Comparativa directa
Parte de una **selección manual de piensos** y muestra sus diferencias de forma estructurada.

---

## Formatos de Excel que intenta leer

La app intenta reconocer:

- formato tabular clásico, con una fila por pienso
- reportes de formulación con bloques `Specification:`
- reportes de formulación con bloques `SP:`
- secciones de ingredientes y análisis, incluidas variantes como `NUTRIENT ANALYSIS`

Si un fichero usa otra maqueta distinta, habrá que ajustar el parser.

---

## Exportaciones a Excel

### En el análisis de búsqueda y ranking
La exportación incluye, según disponibilidad:

- Resumen
- Ranking
- Notas y filtros aplicados
- Detalle del pienso seleccionado
- Fórmula del pienso seleccionado
- Desglose del ranking
- Informe final
- Fragmentos FEDNA

### En la comparativa directa
La exportación incluye:

- Resumen
- Comparativa de nutrientes
- Comparativa de ingredientes
- Una hoja por cada pienso con su fórmula

---

## Papel de FEDNA

FEDNA se usa como **contexto técnico** para enriquecer el chat y la explicación de resultados.

No actúa como motor de cálculo del ranking.
El ranking y las comparativas se construyen con los datos del **Excel cargado**.

---

## Recomendación de uso

1. Cargar el Excel.
2. Seleccionar especie/categoría.
3. Elegir los nutrientes a mostrar.
4. Ejecutar primero el **análisis de búsqueda y ranking** para identificar candidatos.
5. Ejecutar después la **comparativa directa** para revisar los piensos finalistas.
6. Exportar a Excel la salida que quieras conservar o compartir.

---

## Nota final

La app sirve para **filtrar, ordenar, comparar y documentar**.
La decisión final sigue siendo técnica y debe validarse con criterio nutricional, económico y de aplicación práctica.
