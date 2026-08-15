# Optimización de nesting 2D irregular con Algoritmos Genéticos

Proyecto desarrollado para la materia **Algoritmos Evolutivos** de la Especialización en Inteligencia Artificial (CEIA - FIUBA).

El objetivo del trabajo es resolver una instancia de **nesting 2D irregular**, buscando acomodar un conjunto de piezas sobre una tira de ancho fijo utilizando la menor longitud posible.

Para la optimización se implementó un **Algoritmo Genético con DEAP**, mientras que la ubicación geométrica de las piezas se resuelve mediante un decoder determinístico basado en información **NFP (No-Fit Polygon)** e **IFP (Inner-Fit Polygon)**.

---

## Problema

Se utiliza la instancia **SHIRTS** del conjunto de problemas ESICUP.

La instancia contiene:

- 8 tipos de piezas;
- 99 piezas en total;
- ancho fijo de tela de 40 unidades;
- largo disponible del tablero de 1000 unidades;
- orientaciones permitidas de 0° y 180°.

La superficie total ocupada por las piezas es de aproximadamente 2160 unidades cuadradas.

Como el ancho de la tela es fijo, una cota inferior simple para la longitud necesaria puede obtenerse a partir del área:

 
longitud mínima teórica = área total / ancho
                         = 2160 / 40
                         = 54
 

Esta cota representa un límite teórico basado únicamente en área. No considera la forma irregular de las piezas ni los espacios vacíos que inevitablemente aparecen entre ellas.

La función objetivo utilizada en el proyecto es:

 
minimizar longitud de tela utilizada
 

---

## Enfoque general

La solución se dividió en dos partes:

1. un **Algoritmo Genético**, encargado de decidir el orden de colocación y la orientación de cada pieza;
2. un **decoder geométrico**, encargado de determinar la posición de cada pieza sobre la tela.

De esta manera, las coordenadas `(x, y)` no forman parte del cromosoma.

El flujo general es:

 
Algoritmo Genético
        │
        │ orden + orientaciones
        ▼
Decoder geométrico
        │
        │ IFP + NFP + validaciones
        ▼
Layout
        │
        ▼
Longitud utilizada
        │
        ▼
Fitness
 

---

## Representación del individuo

Cada individuo se representa mediante dos bloques:

 
[ orden de colocación | orientaciones ]
 

Para una instancia con `N` piezas, el cromosoma tiene longitud `2N`.

En SHIRTS:

 
N = 99

longitud del cromosoma = 198
 

La primera mitad del cromosoma es una permutación de los identificadores de las piezas:

 
[3, 7, 1, 0, 5, ...]
 

La segunda mitad contiene la orientación asociada a cada instancia:

 
[0, 180, 0, 0, 180, ...]
 

Las orientaciones están indexadas por `instance_id`.

---

## Decoder geométrico

El decoder recibe un orden de piezas y sus orientaciones y construye un layout de forma secuencial.

Para colocar cada nueva pieza utiliza:

- el **IFP** correspondiente a la pieza y su orientación;
- los **NFP** respecto de las piezas que ya fueron colocadas;
- las fronteras de esas geometrías;
- las intersecciones entre fronteras;
- el frente actual del layout.

A partir de esta información se generan posiciones candidatas.

Cada candidato se valida comprobando que:

- la pieza permanezca completamente dentro del tablero;
- no exista solapamiento con piezas previamente colocadas;
- la orientación sea válida.

El contacto entre bordes está permitido.

Entre todos los candidatos válidos se selecciona de manera determinística el que minimiza, en este orden:

1. la nueva longitud total utilizada;
2. la coordenada horizontal mínima de la pieza;
3. la coordenada vertical mínima como criterio de desempate.

El decoder devuelve finalmente:

 
placements
used_length
is_valid
 

La longitud utilizada se calcula como la coordenada `x` máxima alcanzada por las piezas colocadas.

---

## IFP y NFP

### IFP - Inner-Fit Polygon

El IFP representa la región donde puede ubicarse el punto de referencia de una pieza para que esta permanezca dentro del tablero.

En el dataset, el IFP necesita una corrección de referencia para trabajar con el mismo sistema de coordenadas utilizado por el decoder.

### NFP - No-Fit Polygon

El NFP describe las posiciones relativas del punto de referencia de una pieza móvil respecto de una pieza fija.

Su interpretación utilizada en el proyecto es:

 
interior del NFP  -> solapamiento
borde del NFP     -> contacto permitido
exterior del NFP  -> piezas separadas
 

Algunos NFP del dataset son degenerados y aparecen como `LineString` en lugar de polígonos. El código contempla estos casos durante la lectura y validación geométrica.

---

## Algoritmo Genético

La implementación del algoritmo evolutivo se realizó con **DEAP**.

El fitness de cada individuo es:

 
fitness = longitud de tela utilizada
 

Por lo tanto, se trata de un problema de **minimización**.

### Selección

Se utiliza selección por torneo.

### Crossover

Como el cromosoma contiene dos representaciones diferentes, se aplican operadores distintos sobre cada parte.

Para el orden de las piezas se utiliza **Ordered Crossover (OX)**, que permite conservar una permutación válida.

Para las orientaciones se utiliza **crossover uniforme**.

### Mutación

Para el orden se utiliza `mutShuffleIndexes`, manteniendo una permutación válida.

Para las orientaciones se evalúa cada instancia de forma independiente y, cuando corresponde mutarla, se cambia a otra orientación permitida.

### Elitismo

En cada generación se conserva el mejor individuo de la población.

Esto permite evitar que una buena solución se pierda como consecuencia del crossover o de la mutación.

### Cache de fitness

La evaluación de un individuo requiere ejecutar el decoder geométrico completo, que es la parte más costosa del algoritmo.

Por este motivo se implementó un cache utilizando el genoma completo como clave.

Si un individuo ya fue evaluado previamente, su fitness se recupera directamente y se evita ejecutar nuevamente el decoder.

---

## Construcción de soluciones iniciales

Además de individuos aleatorios, se probaron estrategias para comenzar la búsqueda desde regiones más prometedoras.

### Baseline

Como primera referencia se utilizó:

 
orden natural de las piezas
orientación = 0°
 

Resultado aproximado:

 
Longitud utilizada: 79.50
Aprovechamiento:     67.92 %
 

### Heurística por área

Se construyó una solución colocando primero las piezas de mayor área.

Resultado aproximado:

 
Longitud utilizada: 76.94
Aprovechamiento:     70.18 %
 

Esta solución se utilizó posteriormente como punto de partida para generar perturbaciones.

A partir de esas perturbaciones se obtuvo una solución semilla de aproximadamente:

 
Longitud utilizada: 74.78
 

---

## Experimentos

Se realizaron tres configuraciones principales del Algoritmo Genético.

El objetivo no fue solamente buscar un menor fitness, sino también estudiar el efecto de la diversidad poblacional y de las probabilidades de mutación.

---

### Experimento 1 - Configuración inicial

Se utilizó una población pequeña generada alrededor de la mejor solución semilla.

Configuración principal:

 
Población:                  6
Generaciones:               3
Tamaño de torneo:           2
Crossover:                  0.80
Mutación global:            0.40
Mutación interna orden:     0.02
Mutación orientación:       0.02
Elitismo:                   1
 

Mejor resultado aproximado:

 
74.78
 

Durante este experimento la población perdió rápidamente diversidad hasta terminar formada por copias del mismo individuo.

Este comportamiento se interpretó como **convergencia prematura**.

---

### Experimento 2 - Aumento de diversidad

Para reducir la convergencia prematura se aumentó el tamaño de población y se construyó una población inicial con perturbaciones de distinta intensidad alrededor de la solución semilla.

También se aumentaron las probabilidades de mutación.

Configuración principal:

 
Población:                  8
Generaciones:               5
Tamaño de torneo:           2
Crossover:                  0.80
Mutación global:            0.70
Mutación interna orden:     0.04
Mutación orientación:       0.04
Elitismo:                   1
 

Mejor resultado aproximado:

 
74.33
 

La mejor solución apareció ya en la población inicial diversificada.

Durante las generaciones se mantuvo una diversidad elevada, aunque la mutación resultó relativamente agresiva y el fitness promedio empeoró en varias generaciones.

---

### Experimento 3 - Equilibrio entre exploración y explotación

En el tercer experimento se mantuvo una población inicial diversificada, pero se redujo la intensidad de las perturbaciones y de la mutación.

Configuración principal:

 
Población:                  8
Generaciones:               6
Tamaño de torneo:           2
Crossover:                  0.80
Mutación global:            0.50
Mutación interna orden:     0.025
Mutación orientación:       0.025
Elitismo:                   1
 

El mejor individuo apareció durante la generación 2.

Resultado aproximado:

 
Longitud utilizada: 73.78
Aprovechamiento:     73.19 %
 

La mejora respecto del baseline original fue de aproximadamente:

 
7.20 %
 

Esta fue la mejor solución obtenida durante los experimentos.

---

## Resumen de resultados

| Método | Longitud aproximada | Aprovechamiento aproximado |
|---|---:|---:|
| Baseline - orden natural | 79.50 | 67.92 % |
| Heurística por área | 76.94 | 70.18 % |
| Mejor solución semilla | 74.78 | 72.21 % |
| Experimento 1 | 74.78 | 72.21 % |
| Experimento 2 | 74.33 | 72.65 % |
| Experimento 3 | **73.78** | **73.19 %** |

Los resultados muestran que observar únicamente el mejor fitness no es suficiente para interpretar el comportamiento del algoritmo.

En el Experimento 1 se produjo una rápida pérdida de diversidad. En el Experimento 2 se logró preservar la diversidad, aunque con una exploración demasiado agresiva. El Experimento 3 consiguió un mejor equilibrio entre exploración y explotación y produjo la mejor solución encontrada.

---

## Estructura del repositorio

 
AE/
│
├── data/
│   └── raw/
│       ├── shirts.txt
│       ├── shirts.xml
│       └── readme.txt
│
├── notebooks/
│   ├── 00_exploracion.ipynb
│   ├── 01_pruebas_decoder.ipynb
│   └── 03_experimentos_ga.ipynb
│
├── src/
│   └── nesting/
│       ├── __init__.py
│       ├── dataset.py
│       ├── geometry.py
│       ├── decoder.py
│       ├── genetic_algorithm.py
│       └── visualization.py
│
├── tests/
│   ├── test_dataset.py
│   ├── test_geometry.py
│   └── test_decoder.py
│
├── reports/
│   ├── figures/
│   │   └── ga/
│   └── results/
│       └── ga/
│
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
 

---

## Notebooks

### `00_exploracion.ipynb`

Notebook utilizado durante la etapa exploratoria del proyecto.

Incluye la inspección inicial de la instancia SHIRTS, la estructura de los archivos, los tipos de piezas, cantidades, áreas, orientaciones y pruebas preliminares con las geometrías NFP e IFP.

Parte del código desarrollado durante esta etapa fue posteriormente refactorizado y trasladado a los módulos de `src/nesting`.

El objetivo de este notebook es documentar el proceso utilizado para comprender el dataset antes de implementar la solución definitiva.

### `01_pruebas_decoder.ipynb`

Notebook utilizado para desarrollar y validar el decoder geométrico.

Incluye pruebas progresivas con subconjuntos pequeños de piezas y luego con la instancia completa.

También contiene pruebas de rendimiento y análisis realizados durante el desarrollo para detectar operaciones costosas y mejorar la generación y validación de posiciones candidatas.

### `02_experimentos_ga.ipynb`

Notebook principal de experimentación.

Incluye:

- representación del individuo;
- generación de cromosomas;
- heurística por área;
- evaluación del fitness;
- cache de evaluaciones;
- pruebas de crossover y mutación;
- construcción de soluciones semilla;
- baseline;
- tres configuraciones experimentales del GA;
- seguimiento del fitness;
- seguimiento de diversidad genética;
- curvas de convergencia;
- comparación entre experimentos;
- validación del mejor layout;
- guardado de resultados y figuras.

---

## Módulos principales

### `dataset.py`

Se encarga de leer la instancia ESICUP desde `shirts.xml`.

Define las estructuras:

 
PieceType
PieceInstance
NestingProblem
 

También:

- lee las geometrías;
- carga los tipos de piezas;
- expande los tipos en las 99 instancias físicas;
- construye las tablas de consulta de NFP;
- construye las tablas de consulta de IFP;
- carga la geometría del tablero.

---

### `geometry.py`

Contiene las operaciones geométricas utilizadas por el decoder.

Entre ellas:

- orientación de piezas;
- traslación de piezas;
- recuperación y corrección del IFP;
- recuperación de NFP relativos;
- construcción de NFP absolutos;
- extracción de fronteras;
- validación de posiciones;
- clasificación de relaciones entre piezas;
- detección de solapamientos;
- validación de layouts completos;
- cálculo de longitud utilizada;
- extracción de coordenadas de geometrías Shapely.

---

### `decoder.py`

Implementa el decoder determinístico.

Recibe:

 
orden + orientaciones
 

y devuelve un layout.

Para cada pieza:

1. valida la orientación;
2. obtiene su IFP;
3. construye los NFP respecto de las piezas ya colocadas;
4. genera posiciones candidatas;
5. filtra candidatos mediante IFP y NFP;
6. valida geométricamente cada candidato;
7. selecciona la mejor posición;
8. agrega la pieza al layout.

---

### `genetic_algorithm.py`

Contiene la implementación del Algoritmo Genético.

Incluye:

- separación del cromosoma;
- generación de genomas aleatorios;
- heurística por área;
- validación de individuos;
- creación de claves para cache;
- evaluación del fitness;
- Ordered Crossover;
- crossover uniforme;
- mutación del orden;
- mutación de orientaciones;
- configuración de DEAP;
- creación de individuos;
- generación de perturbaciones;
- construcción de poblaciones;
- selección por torneo;
- elitismo;
- ejecución completa del GA;
- registro del historial de cada generación.

---

### `visualization.py`

Contiene las funciones utilizadas para representar gráficamente los layouts producidos por el decoder.

Las figuras muestran:

- las piezas colocadas;
- la región de tela utilizada;
- el ancho de la tira;
- la longitud final utilizada.

---

## Optimización del decoder

Una de las principales dificultades del proyecto fue el costo computacional del decoder.

Cada evaluación del fitness requiere construir un layout completo de hasta 99 piezas y realizar múltiples operaciones geométricas con Shapely.

Durante el desarrollo se incorporaron distintas optimizaciones.

### Bounding boxes

Antes de realizar una intersección geométrica se verifica si las bounding boxes pueden intersectarse.

Esto permite descartar rápidamente muchos casos sin ejecutar operaciones más costosas de Shapely.

### Generación directa de coordenadas

Las posiciones candidatas se representan mediante pares `(x, y)` y se deduplican durante la generación.

Esto evita crear objetos `Point` innecesarios.

### Frente actual del layout

Además de utilizar vértices e intersecciones de IFP y NFP, se incorporó como fuente de candidatos el frente vertical correspondiente a la longitud actualmente utilizada.

Esto permitió generar posiciones relevantes que no siempre aparecían utilizando únicamente las fronteras geométricas.

### Cache del fitness

Cada genoma evaluado se almacena junto con su fitness.

Si el mismo individuo vuelve a aparecer durante la evolución, el decoder no se ejecuta nuevamente.

---

## Instalación

El proyecto fue desarrollado utilizando **Python 3.11**.

Clonar el repositorio y posicionarse en la raíz:

  
cd AE
 

Crear un entorno virtual:

  
python -m venv .venv
 

Activarlo en Windows  :

  
.\.venv\Scripts\Activate.ps1
 

Instalar las dependencias:

  
python -m pip install -r requirements.txt
 

Instalar el proyecto en modo editable:

  
python -m pip install -e .
 

Esto permite importar los módulos directamente como:

 python
from nesting.dataset import load_problem
from nesting.decoder import decode_solution
from nesting.genetic_algorithm import run_genetic_algorithm
 

---

## Ejecución de tests

Los tests automáticos incluidos actualmente cubren:

- carga del dataset SHIRTS;
- cantidad de tipos e instancias;
- orientaciones permitidas;
- identificadores de instancias;
- rotación y traslación de piezas;
- comportamiento de NFP;
- comportamiento de IFP;
- validación de posiciones;
- detección de solapamientos;
- cálculo de longitud utilizada;
- validación de layouts;
- colocación de piezas mediante el decoder;
- decodificación de subconjuntos de piezas;
- validación de órdenes y orientaciones inválidas.

Para ejecutar la suite:

  
python -m pytest -v
 

Actualmente no se incluyeron tests unitarios específicos para `genetic_algorithm.py`.

El comportamiento del Algoritmo Genético y de sus operadores se analiza principalmente en `02_experimentos_ga.ipynb`, donde se prueban la representación, crossover, mutación, poblaciones y evolución de los distintos experimentos.

---

## Ejecución de los notebooks

Los notebooks se encuentran en:

 
notebooks/
 

Se recomienda utilizar el entorno virtual del proyecto como kernel de Jupyter.

El orden de lectura sugerido es:

 
00_exploracion.ipynb
        ↓
01_pruebas_decoder.ipynb
        ↓
02_experimentos_ga.ipynb
 

Los dos primeros notebooks documentan principalmente el proceso de exploración y desarrollo.

El tercer notebook contiene la experimentación final del Algoritmo Genético.

---

## Resultados generados

Los resultados numéricos de los experimentos se guardan en:

 
reports/results/ga/
 

Para cada experimento se genera una carpeta:

 
experiment_1/
experiment_2/
experiment_3/
 

con archivos como:

 
history.csv
best_genome.json
parameters.json
summary.json
 

Además se generan archivos de resumen:

 
experiments_summary.csv
best_solution.json
 

Las figuras se almacenan en:

 
reports/figures/ga/
 

Entre ellas:

 
experiments_convergence_comparison.png
experiments_diversity_comparison.png
best_layout_final.png
 

También se almacenan las curvas y layouts correspondientes a cada experimento.

---

## Reproducibilidad

Para facilitar la comparación entre configuraciones se utilizaron semillas aleatorias fijas en los experimentos.

El Algoritmo Genético utiliza aleatoriedad tanto para la creación de poblaciones como para selección, crossover y mutación.

El decoder, en cambio, es determinístico: para un mismo orden y conjunto de orientaciones devuelve siempre el mismo layout.

Esto permite que las diferencias observadas entre individuos provengan de las decisiones del Algoritmo Genético y no de aleatoriedad dentro del decoder.

---

## Limitaciones

La principal limitación encontrada es el costo computacional de la evaluación.

Cada individuo requiere ejecutar el decoder sobre las 99 piezas, por lo que aumentar mucho el tamaño de población o la cantidad de generaciones incrementa rápidamente el tiempo total de ejecución.

Por este motivo los experimentos se realizaron con poblaciones relativamente pequeñas.

Además, el decoder utiliza una estrategia determinística de colocación. Por lo tanto, para un orden y orientaciones determinados se explora una única forma de construir el layout.

---

## Posibles mejoras

Como continuación del trabajo se podrían evaluar:

- poblaciones de mayor tamaño;
- mayor cantidad de generaciones;
- múltiples ejecuciones independientes para cada configuración;
- estrategias adaptativas de mutación;
- mecanismos adicionales de preservación de diversidad;
- búsqueda local aplicada a los mejores individuos;
- paralelización de las evaluaciones;
- nuevas estrategias de generación de posiciones candidatas;
- mejoras adicionales en el decoder;
- comparación con otras metaheurísticas;
- combinación del Algoritmo Genético con técnicas de búsqueda local.

---

## Conclusiones

Se implementó una solución completa para el problema de nesting irregular de la instancia SHIRTS combinando un Algoritmo Genético con un decoder geométrico basado en NFP e IFP.

El uso de una heurística inicial permitió partir de una región del espacio de búsqueda considerablemente mejor que el orden original.

Los experimentos también mostraron la importancia de la diversidad poblacional.

El primer experimento presentó convergencia prematura. El segundo permitió recuperar diversidad mediante una estrategia de exploración más agresiva. Finalmente, el tercer experimento logró un mejor equilibrio entre exploración y explotación.

La mejor solución encontrada utilizó aproximadamente:

 
73.78 unidades de longitud
 

frente a aproximadamente:

 
79.50 unidades
 

del baseline inicial.

Esto representa una mejora aproximada del:

 
7.20 %
 

y un aprovechamiento de material cercano al:

 
73.19 %
 

La solución final fue validada geométricamente para verificar que las piezas permanecieran dentro del tablero y no existieran solapamientos con área positiva.

---

## Tecnologías utilizadas

- Python 3.11
- DEAP
- Shapely
- NumPy
- Pandas
- Matplotlib
- PyYAML
- Jupyter
- pytest
