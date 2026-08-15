# GA con DEAP
from __future__ import annotations

import random
from typing import Sequence

from nesting.dataset import NestingProblem
from nesting.decoder import decode_solution
from deap import tools, base, creator


def split_individual(
    individual: Sequence[int],
    n_pieces: int,
) -> tuple[list[int], list[int]]:
    """
    Separa un cromosoma en sus dos componentes:

    - orden de colocación;
    - orientación de cada instancia.

    La primera mitad es una permutación de instance_id.
    La segunda mitad está indexada por instance_id.
    """

    expected_length = 2 * n_pieces

    if len(individual) != expected_length:
        raise ValueError(
            f"El individuo debe tener longitud "
            f"{expected_length}, pero tiene "
            f"{len(individual)}."
        )

    order = list(
        individual[:n_pieces]
    )

    orientations = list(
        individual[n_pieces:]
    )

    return order, orientations


def create_random_genome(
    problem: NestingProblem,
    rng: random.Random | None = None,
) -> list[int]:
    """
    Crea un cromosoma aleatorio válido.

    Estructura:

        [orden | orientaciones]

    donde:

    - orden es una permutación de las instancias;
    - orientaciones está indexado por instance_id.
    """

    if rng is None:
        rng = random

    n_pieces = len(
        problem.piece_instances
    )

    order = list(
        range(n_pieces)
    )

    rng.shuffle(order)

    orientations = [
        rng.choice(
            instance.allowed_orientations
        )
        for instance in problem.piece_instances
    ]

    return (
        order
        + orientations
    )


def create_area_heuristic_genome(
    problem: NestingProblem,
) -> list[int]:
    """
    Crea un cromosoma utilizando como orden inicial
    la heurística de mayor área primero.

    La orientación inicial elegida es la primera
    permitida para cada instancia.
    """

    ordered_instances = sorted(
        problem.piece_instances,
        key=lambda instance: problem.geometries[
            instance.polygon_id
        ].area,
        reverse=True,
    )

    order = [
        instance.instance_id
        for instance in ordered_instances
    ]

    orientations = [
        int(
            instance.allowed_orientations[0]
        )
        for instance in problem.piece_instances
    ]

    return (
        order
        + orientations
    )


def validate_genome(
    problem: NestingProblem,
    individual: Sequence[int],
) -> tuple[bool, list[str]]:
    """
    Comprueba que un cromosoma sea válido antes
    de enviarlo al decoder.
    """

    errors: list[str] = []

    n_pieces = len(
        problem.piece_instances
    )

    try:
        order, orientations = (
            split_individual(
                individual=individual,
                n_pieces=n_pieces,
            )
        )

    except ValueError as error:
        return False, [str(error)]

    expected_ids = set(
        range(n_pieces)
    )

    if set(order) != expected_ids:
        errors.append(
            "El orden no es una permutación "
            "válida de las instancias."
        )

    if len(order) != len(set(order)):
        errors.append(
            "El orden contiene instancias "
            "duplicadas."
        )

    for instance in problem.piece_instances:

        instance_id = (
            instance.instance_id
        )

        angle = int(
            orientations[instance_id]
        )

        if (
            angle
            not in instance.allowed_orientations
        ):
            errors.append(
                f"Orientación {angle}° inválida "
                f"para la instancia "
                f"{instance_id}."
            )

    return (
        len(errors) == 0,
        errors,
    )


def genome_key(
    individual: Sequence[int],
) -> tuple[int, ...]:
    """
    Convierte un individuo en una clave inmutable.

    Se utilizará posteriormente para cachear el fitness
    y evitar decodificar dos veces exactamente la misma
    solución.
    """

    return tuple(
        int(gene)
        for gene in individual
    )



FitnessValue = tuple[float]
FitnessCache = dict[tuple[int, ...], FitnessValue]


def evaluate_individual(
    individual: Sequence[int],
    problem: NestingProblem,
    cache: FitnessCache | None = None,
    invalid_penalty: float | None = None,
) -> FitnessValue:
    """
    Evalúa un individuo utilizando el decoder geométrico.

    El objetivo es minimizar la longitud de tela utilizada.

    Si el individuo ya fue evaluado, el resultado se
    recupera del cache y se evita ejecutar nuevamente
    el decoder.

    La función devuelve una tupla porque DEAP espera
    que el fitness tenga este formato.
    """

    key = genome_key(
        individual
    )

    # --------------------------------------------------
    # 1. Revisar cache
    # --------------------------------------------------

    if cache is not None and key in cache:
        return cache[key]

    # --------------------------------------------------
    # 2. Validar cromosoma
    # --------------------------------------------------

    is_valid, errors = validate_genome(
        problem=problem,
        individual=individual,
    )

    if invalid_penalty is None:
        invalid_penalty = (
            problem.board_geometry.bounds[2]
            + 1.0
        )

    if not is_valid:

        fitness = (
            float(invalid_penalty),
        )

        if cache is not None:
            cache[key] = fitness

        return fitness

    # --------------------------------------------------
    # 3. Separar orden y orientaciones
    # --------------------------------------------------

    n_pieces = len(
        problem.piece_instances
    )

    order, orientations = split_individual(
        individual=individual,
        n_pieces=n_pieces,
    )

    # --------------------------------------------------
    # 4. Ejecutar decoder
    # --------------------------------------------------

    try:

        result = decode_solution(
            problem=problem,
            order=order,
            orientations=orientations,
        )

        fitness = (
            float(result.used_length),
        )

    except RuntimeError:

        # Si excepcionalmente el decoder no logra
        # construir una solución, penalizamos el
        # individuo en lugar de detener todo el GA.
        fitness = (
            float(invalid_penalty),
        )

    # --------------------------------------------------
    # 5. Guardar resultado
    # --------------------------------------------------

    if cache is not None:
        cache[key] = fitness

    return fitness


def mate_individuals(
    individual_1: list[int],
    individual_2: list[int],
    n_pieces: int,
) -> tuple[list[int], list[int]]:
    """
    Cruza dos individuos respetando la estructura
    del cromosoma.

    - Para el orden se utiliza Ordered Crossover (OX),
      que conserva una permutación válida.
    - Para las orientaciones se utiliza crossover
      uniforme, intercambiando genes correspondientes
      a la misma instancia.
    """

    # --------------------------------------------------
    # 1. Separar ambas partes del cromosoma
    # --------------------------------------------------

    order_1 = list(
        individual_1[:n_pieces]
    )

    order_2 = list(
        individual_2[:n_pieces]
    )

    orientations_1 = list(
        individual_1[n_pieces:]
    )

    orientations_2 = list(
        individual_2[n_pieces:]
    )

    # --------------------------------------------------
    # 2. Crossover del orden
    # --------------------------------------------------

    tools.cxOrdered(
        order_1,
        order_2,
    )

    # --------------------------------------------------
    # 3. Crossover de orientaciones
    # --------------------------------------------------

    tools.cxUniform(
        orientations_1,
        orientations_2,
        indpb=0.5,
    )

    # --------------------------------------------------
    # 4. Reconstruir los individuos
    # --------------------------------------------------

    individual_1[:] = (
        order_1
        + orientations_1
    )

    individual_2[:] = (
        order_2
        + orientations_2
    )

    return (
        individual_1,
        individual_2,
    )


def mutate_individual(
    individual: list[int],
    problem: NestingProblem,
    order_indpb: float = 0.02,
    orientation_indpb: float = 0.02,
) -> tuple[list[int]]:
    """
    Muta un individuo respetando las restricciones
    de cada parte del cromosoma.

    Orden:
        se utiliza mutShuffleIndexes, que mantiene una
        permutación válida.

    Orientaciones:
        cada instancia puede cambiar aleatoriamente a
        otra orientación permitida.
    """

    n_pieces = len(
        problem.piece_instances
    )

    order = list(
        individual[:n_pieces]
    )

    orientations = list(
        individual[n_pieces:]
    )

    # --------------------------------------------------
    # 1. Mutación del orden
    # --------------------------------------------------

    tools.mutShuffleIndexes(
        order,
        indpb=order_indpb,
    )

    # --------------------------------------------------
    # 2. Mutación de orientaciones
    # --------------------------------------------------

    for instance in problem.piece_instances:

        instance_id = (
            instance.instance_id
        )

        if (
            random.random()
            < orientation_indpb
        ):

            current_angle = (
                orientations[instance_id]
            )

            alternatives = [
                angle
                for angle
                in instance.allowed_orientations
                if angle != current_angle
            ]

            if alternatives:
                orientations[instance_id] = (
                    random.choice(
                        alternatives
                    )
                )

    # --------------------------------------------------
    # 3. Reconstruir cromosoma
    # --------------------------------------------------

    individual[:] = (
        order
        + orientations
    )

    return (individual,)


def setup_deap_types() -> None:
    """
    Crea los tipos utilizados por DEAP.

    Se realizan comprobaciones previas para evitar errores
    al recargar el módulo desde un notebook con autoreload.
    """

    if not hasattr(
        creator,
        "FitnessMinNesting",
    ):
        creator.create(
            "FitnessMinNesting",
            base.Fitness,
            weights=(-1.0,), # indica que es minimización
        )

    if not hasattr(
        creator,
        "IndividualNesting",
    ):
        creator.create(
            "IndividualNesting",
            list,
            fitness=creator.FitnessMinNesting,
        )


def create_deap_individual(
    genome: Sequence[int],
):
    """
    Convierte un cromosoma común en un individuo DEAP.
    """

    setup_deap_types()

    return creator.IndividualNesting(
        list(genome)
    )

def create_toolbox(
    problem: NestingProblem,
    cache: FitnessCache,
    tournament_size: int = 3,
    order_indpb: float = 0.02,
    orientation_indpb: float = 0.02,
):
    """
    Configura el Toolbox de DEAP para el problema
    de nesting.
    """

    setup_deap_types()

    n_pieces = len(
        problem.piece_instances
    )

    toolbox = base.Toolbox()

    # Fitness
    toolbox.register(
        "evaluate",
        evaluate_individual,
        problem=problem,
        cache=cache,
    )

    # Crossover
    toolbox.register(
        "mate",
        mate_individuals,
        n_pieces=n_pieces,
    )

    # Mutación
    toolbox.register(
        "mutate",
        mutate_individual,
        problem=problem,
        order_indpb=order_indpb,
        orientation_indpb=(
            orientation_indpb
        ),
    )

    # Selección
    toolbox.register(
        "select",
        tools.selTournament,
        tournsize=tournament_size,
    )

    return toolbox



def create_perturbed_genome(
    problem: NestingProblem,
    base_genome: Sequence[int],
    n_order_swaps: int = 3,
    orientation_mutation_prob: float = 0.05,
    rng: random.Random | None = None,
) -> list[int]:
    """
    Genera un individuo cercano a una solución conocida.

    La diversidad se introduce mediante:

    - intercambios entre posiciones del orden;
    - cambios ocasionales de orientación.

    La estructura del cromosoma permanece válida.
    """

    if rng is None:
        rng = random

    n_pieces = len(
        problem.piece_instances
    )

    order, orientations = split_individual(
        individual=base_genome,
        n_pieces=n_pieces,
    )

    # --------------------------------------------------
    # 1. Perturbar el orden mediante swaps
    # --------------------------------------------------

    for _ in range(n_order_swaps):

        first_index, second_index = (
            rng.sample(
                range(n_pieces),
                2,
            )
        )

        (
            order[first_index],
            order[second_index],
        ) = (
            order[second_index],
            order[first_index],
        )

    # --------------------------------------------------
    # 2. Perturbar orientaciones
    # --------------------------------------------------

    for instance in problem.piece_instances:

        if (
            rng.random()
            >= orientation_mutation_prob
        ):
            continue

        instance_id = (
            instance.instance_id
        )

        current_angle = (
            orientations[instance_id]
        )

        alternatives = [
            angle
            for angle
            in instance.allowed_orientations
            if angle != current_angle
        ]

        if alternatives:

            orientations[instance_id] = (
                rng.choice(
                    alternatives
                )
            )

    return (
        order
        + orientations
    )





def create_mixed_population(
    problem: NestingProblem,
    population_size: int,
    seed_genome: Sequence[int],
    n_perturbed: int,
    n_order_swaps: int = 3,
    orientation_mutation_prob: float = 0.03,
    rng: random.Random | None = None,
) -> list:
    """
    Crea una población inicial mixta.

    La población contiene:

    - la mejor solución conocida;
    - varias perturbaciones de esa solución;
    - individuos aleatorios para mantener diversidad.
    """

    if rng is None:
        rng = random

    if population_size < 1:
        raise ValueError(
            "population_size debe ser mayor que cero."
        )

    if n_perturbed > population_size - 1:
        raise ValueError(
            "n_perturbed debe dejar espacio para "
            "el individuo semilla."
        )

    setup_deap_types()

    population = [
        create_deap_individual(
            seed_genome
        )
    ]

    # Vecinos de la mejor solución conocida.
    for _ in range(n_perturbed):

        genome = create_perturbed_genome(
            problem=problem,
            base_genome=seed_genome,
            n_order_swaps=n_order_swaps,
            orientation_mutation_prob=(
                orientation_mutation_prob
            ),
            rng=rng,
        )

        population.append(
            create_deap_individual(
                genome
            )
        )

    # El resto son individuos aleatorios.
    while len(population) < population_size:

        genome = create_random_genome(
            problem=problem,
            rng=rng,
        )

        population.append(
            create_deap_individual(
                genome
            )
        )

    return population



def run_genetic_algorithm(
    population: list,
    toolbox,
    cache: FitnessCache,
    n_generations: int = 3,
    crossover_probability: float = 0.8,
    mutation_probability: float = 0.4,
    elite_size: int = 1,
) -> tuple[list, object, list[dict]]:
    """
    Ejecuta el ciclo completo del algoritmo genético.

    En cada generación:

    1. conserva los mejores individuos mediante elitismo;
    2. selecciona padres por torneo;
    3. aplica crossover;
    4. aplica mutación;
    5. evalúa únicamente individuos con fitness inválido;
    6. registra estadísticas de convergencia.

    Devuelve:
        - población final;
        - mejor individuo encontrado;
        - historial de evolución.
    """

    import statistics
    import time

    if elite_size < 1:
        raise ValueError(
            "elite_size debe ser al menos 1."
        )

    if elite_size >= len(population):
        raise ValueError(
            "elite_size debe ser menor que "
            "el tamaño de la población."
        )

    history: list[dict] = []

    # --------------------------------------------------
    # Evaluación inicial
    # --------------------------------------------------

    start_time = time.perf_counter()

    cache_before = len(cache)

    for individual in population:

        if not individual.fitness.valid:
            individual.fitness.values = (
                toolbox.evaluate(
                    individual
                )
            )

    cache_after = len(cache)

    fitness_values = [
        individual.fitness.values[0]
        for individual in population
    ]

    history.append(
        {
            "generation": 0,
            "best": min(fitness_values),
            "mean": statistics.mean(
                fitness_values
            ),
            "worst": max(fitness_values),
            "new_evaluations": (
                cache_after
                - cache_before
            ),
            "unique_genomes": len({
                genome_key(individual)
                for individual in population
            }),
            "elapsed_time": (
                time.perf_counter()
                - start_time
            ),
        }
    )

    # --------------------------------------------------
    # Generaciones
    # --------------------------------------------------

    for generation in range(
        1,
        n_generations + 1,
    ):

        generation_start = (
            time.perf_counter()
        )

        cache_before = len(cache)

        # ----------------------------------------------
        # 1. Elitismo
        # ----------------------------------------------

        elites = [
            toolbox.clone(individual)
            for individual in tools.selBest(
                population,
                elite_size,
            )
        ]

        # ----------------------------------------------
        # 2. Selección
        # ----------------------------------------------

        selected = toolbox.select(
            population,
            len(population) - elite_size,
        )

        offspring = [
            toolbox.clone(individual)
            for individual in selected
        ]

        # ----------------------------------------------
        # 3. Crossover
        # ----------------------------------------------

        for first, second in zip(
            offspring[::2],
            offspring[1::2],
        ):

            if (
                random.random()
                < crossover_probability
            ):

                toolbox.mate(
                    first,
                    second,
                )

                if first.fitness.valid:
                    del first.fitness.values

                if second.fitness.valid:
                    del second.fitness.values

        # ----------------------------------------------
        # 4. Mutación
        # ----------------------------------------------

        for individual in offspring:

            if (
                random.random()
                < mutation_probability
            ):

                toolbox.mutate(
                    individual
                )

                if individual.fitness.valid:
                    del individual.fitness.values

        # ----------------------------------------------
        # 5. Evaluar solamente individuos nuevos
        # ----------------------------------------------

        for individual in offspring:

            if not individual.fitness.valid:

                individual.fitness.values = (
                    toolbox.evaluate(
                        individual
                    )
                )

        # ----------------------------------------------
        # 6. Nueva población
        # ----------------------------------------------

        population = (
            elites
            + offspring
        )

        # ----------------------------------------------
        # 7. Estadísticas
        # ----------------------------------------------

        fitness_values = [
            individual.fitness.values[0]
            for individual in population
        ]

        cache_after = len(cache)

        generation_time = (
            time.perf_counter()
            - generation_start
        )

        history.append(
            {
                "generation": generation,
                "best": min(
                    fitness_values
                ),
                "mean": statistics.mean(
                    fitness_values
                ),
                "worst": max(
                    fitness_values
                ),
                "new_evaluations": (
                    cache_after
                    - cache_before
                ),
                "unique_genomes": len({
                    genome_key(individual)
                    for individual in population
                }),

                "elapsed_time": (
                    generation_time
                ),
            }
        )

        print(
            f"Generación {generation:02d} | "
            f"best={min(fitness_values):.2f} | "
            f"mean={statistics.mean(fitness_values):.2f} | "
            f"diversidad={len({genome_key(ind) for ind in population})} | "
            f"evals nuevas={cache_after - cache_before} | "
            f"tiempo={generation_time:.2f} s"
        )

    # --------------------------------------------------
    # Mejor solución global
    # --------------------------------------------------

    best_individual = tools.selBest(
        population,
        1,
    )[0]

    return (
        population,
        best_individual,
        history,
    )


