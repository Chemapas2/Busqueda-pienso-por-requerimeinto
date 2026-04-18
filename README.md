# FEDNA Feed Recommender

Aplicación web en Streamlit para relacionar perfiles nutricionales FEDNA con formulaciones de pienso cargadas desde Excel y recomendar los piensos más adecuados ordenados por aptitud.

## Qué hace

- Selecciona una categoría exacta entre:
  - Rumiantes de carne
  - Rumiantes de leche
  - Reposición de rumiantes
  - Avicultura
  - Porcino
- Carga un Excel mensual de formulación.
- Normaliza nutrientes y columnas.
- Responde preguntas en lenguaje natural desde un chat con cuadro de consulta visible, editable y con propuestas rápidas reutilizables.
- Calcula un ranking de aptitud nutricional y devuelve el Top N.
- Permite limitar el ranking a los nutrientes seleccionados por el usuario.
- Muestra detalle de cada pienso:
  - fórmula completa de ingredientes y porcentajes cuando el Excel la contiene
  - comparación de nutrientes frente al requerimiento activo
  - límites internos de fórmula cuando existen
- Genera un informe resumen descargable en Markdown.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run main.py
```

## Estructura recomendada del proyecto

```text
.
├── main.py
├── requirements.txt
├── README.md
└── fedna_manuals/
    ├── Normas PORCINO_2013rev2_0.pdf
    ├── NORMAS RUMIANTES CEBO 2008-v1.pdf
    ├── NORMAS_FEDNA_AVES_2018v.pdf
    ├── NORMAS_RECRIA_2010.pdf
    └── NORMAS_RUMIANTES_LECHE_2009rev_0.pdf
```

Los PDF no se incluyen en el repositorio por defecto. Deben colocarse manualmente en `./fedna_manuals/` o cargarse desde la propia app en el uploader opcional de PDF.

## Formato esperado del Excel

La app soporta **dos formatos**.

### 1) Formato tabular clásico

Una fila por pienso. Columnas mínimas recomendadas:

- `Pienso` o `Nombre pienso`
- `Precio` o `Cost/tonne`
- columnas de nutrientes, por ejemplo:
  - `PROT_BRU`
  - `FND`
  - `LYS`
  - `MET`
  - `THR`
  - `CA`
  - `P_`
  - `AVP_AV`
  - `NE_SW`
  - `ME_SW`
  - `EMAN`
  - `UFC`
  - `UFL`

Opcionales:

- columnas de ingredientes con prefijos tipo:
  - `ING_Maiz`
  - `ING_Harina_soja`
  - `ING_Cebada`
- columnas de límites por nutriente:
  - `PROT_BRU_min`
  - `PROT_BRU_max`
  - `LYS_min`
  - `LYS_max`
  - `CA_min`
  - `CA_max`

Ejemplo mínimo:

| Pienso | Precio | PROT_BRU | FND | LYS | CA | NE_SW |
|---|---:|---:|---:|---:|---:|---:|
| Prestarter A | 338.28 | 17.7 | 13.1 | 1.23 | 0.70 | 2445 |
| Crecimiento B | 300.89 | 18.8 | 11.8 | 1.17 | 0.79 | 2575 |

### 2) Formato reporte de formulación tipo Multi-Mix

La app también soporta reportes exportados como bloques de texto en Excel con secciones como:

- `Specification`
- `Included Raw Materials`
- `Analysis`

Ese es el formato del archivo de ejemplo que has cargado en esta conversación. El parser extrae automáticamente:

- nombre del pienso
- coste por tonelada
- fórmula de ingredientes y porcentajes
- análisis nutricional
- límites de ingredientes y nutrientes cuando aparecen en el reporte

## Nutrientes reconocidos

La app normaliza alias frecuentes hacia códigos internos. Algunos ejemplos:

- `Proteína bruta`, `PB` → `PROT_BRU`
- `Fibra bruta`, `FB` → `FIBRA_BR`
- `Almidón` → `ALM_EWER`
- `Calcio` → `CA`
- `Fósforo total` → `P_`
- `Fósforo digestible/disponible` → `AVP_AV`
- `Lisina` → `LYS`
- `Metionina` → `MET`
- `Met+Cys` → `MET_CYS`
- `Treonina` → `THR`
- `Triptófano` → `TRP`
- `EMAn` → `EMAN`
- `UFC` → `UFC`
- `UFL` → `UFL`

## Dónde colocar o cargar los manuales FEDNA

Tienes dos opciones:

### Opción A. Carpeta local

Coloca los PDF en:

```text
./fedna_manuals/
```

Los nombres de archivo deberían contener pistas como:

- `porcino`
- `aves` o `avicultura`
- `recria` o `recría`
- `leche`
- `cebo`

### Opción B. Subida desde la interfaz

En la barra lateral hay un uploader opcional para cargar uno o varios PDF FEDNA. Si alguno falla o no tiene texto extraíble, la aplicación lo marcará como incidencia pero no detendrá el flujo principal.

## Cómo usa FEDNA la app

La app trabaja con dos capas:

1. **Perfiles FEDNA integrados** por categoría para poder rankear sin depender de un parser complejo de tablas PDF.
2. **Recuperación de fragmentos** desde los PDF FEDNA cargados para contextualizar la respuesta del chat.

Esto permite tener una app explicable y robusta sin depender de una API externa.

## Uso del chat

La interfaz incluye:

- un selector de propuestas editables de consulta
- un cuadro de texto siempre visible para escribir o modificar la pregunta
- botón **Buscar y rankear**
- botón **Refrescar resultados** para repetir la búsqueda actual
- botón **Nueva búsqueda** para limpiar historial y resultados

Ejemplos de preguntas válidas:

- `Quiero un pienso de crecimiento con lisina > 1.0 y proteína entre 16 y 18`
- `Necesito una opción barata con calcio >= 0.7 y sin trigo`
- `Dame el top 5 para porcino priorizando lisina y energía`
- `Para recría, quiero más proteína y menos fibra`
- `Busca una opción de broiler con EMAn alta y calcio dentro de rango`

Qué interpreta el chat:

- comparadores numéricos (`>`, `>=`, `<`, `<=`, `=`)
- rangos (`entre X y Y`)
- filtros de precio
- preferencia por menor coste (`barato`, `económico`)
- inclusión o exclusión simple de ingredientes (`con soja`, `sin trigo`, `evitar cebada`)

## Lógica de ranking

La aptitud se calcula con una puntuación por nutriente según su ajuste a un requerimiento:

- mínimo
- máximo
- objetivo
- rango

La puntuación final es una media ponderada de los nutrientes activos.

### Regla importante

Si el usuario selecciona nutrientes en el selector, el ranking se centra en ellos. Si además en el chat se especifica un nutriente explícito, ese nutriente se incorpora al ranking aunque no estuviera seleccionado inicialmente.

## Robustez incluida

El código contempla errores típicos:

- Excel sin nombre de pienso identificable
- falta de precio
- columnas vacías
- valores nulos
- nutrientes no presentes en el Excel
- PDFs FEDNA no disponibles o con texto no extraíble, sin bloquear la app
- filtros que dejan el conjunto de resultados vacío

## Limitaciones

- Los perfiles FEDNA integrados son **representativos**, no sustituyen el ajuste fino por fase, genética, consumo, estado sanitario o estrategia de producción.
- El parser de lenguaje natural es determinista y no pretende sustituir una revisión técnica completa.
- Si el Excel no contiene los nutrientes relevantes para la categoría, el ranking se limita a la intersección disponible.
- Los PDF se usan para recuperación de contexto textual, no para un parsing exhaustivo de todas las tablas FEDNA.

## Publicación en GitHub

Pasos recomendados:

```bash
git init
git add main.py requirements.txt README.md
git commit -m "Initial FEDNA Streamlit app"
```

Si vas a desplegar en Streamlit Community Cloud:

- sube `main.py`, `requirements.txt` y `README.md`
- añade la carpeta `fedna_manuals/` si tienes permiso para incluir los PDF
- en caso contrario, usa el uploader de manuales dentro de la app
