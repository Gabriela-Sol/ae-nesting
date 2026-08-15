# Dado orden + orientaciones, colocar todas las piezas
from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry

from nesting.dataset import NestingProblem, PieceInstance
from nesting.geometry import (
    calculate_used_length,
    geometry_boundary,
    get_absolute_nfp,
    get_ifp_geometry,
    get_oriented_piece,
    is_valid_piece_placement,
    place_piece,
    point_is_forbidden_by_nfp,
    extract_coordinates_from_geometry,
)


Bounds = tuple[
    float,
    float,
    float,
    float,
]


def _bounds_overlap(
    first_bounds: Bounds,
    second_bounds: Bounds,
) -> bool:
    """
    Indica si dos bounding boxes se intersectan
    o se tocan.

    Esta comprobación es mucho más barata que realizar
    una operación geométrica con Shapely.
    """

    (
        first_min_x,
        first_min_y,
        first_max_x,
        first_max_y,
    ) = first_bounds

    (
        second_min_x,
        second_min_y,
        second_max_x,
        second_max_y,
    ) = second_bounds

    return not (
        first_max_x < second_min_x
        or second_max_x < first_min_x
        or first_max_y < second_min_y
        or second_max_y < first_min_y
    )

def _coordinates_inside_bounds(
    x: float,
    y: float,
    bounds: Bounds,
) -> bool:
    """
    Comprueba si unas coordenadas (x, y) pertenecen
    a una bounding box.

    Se utilizan floats en lugar de acceder repetidamente
    a Point.x y Point.y de Shapely.
    """

    min_x, min_y, max_x, max_y = bounds

    return (
        min_x <= x <= max_x
        and min_y <= y <= max_y
    )


@dataclass
class Placement:
    """
    Resultado de colocar una pieza en la tela.
    """

    instance_id: int
    piece_id: str
    polygon_id: str
    angle: int

    reference_x: float
    reference_y: float

    geometry: BaseGeometry


@dataclass
class DecodeResult:
    """
    Resultado completo de decodificar una solución.
    """

    placements: list[Placement]
    used_length: float
    is_valid: bool


def generate_candidate_points(
    ifp_geometry: BaseGeometry,
    forbidden_nfps: list[BaseGeometry],
    front_reference_x: float | None = None,
    decimal_places: int = 8,
) -> list[tuple[float, float]]:
    """
    Genera posiciones candidatas como pares (x, y).

    Se consideran:
    1. vértices del IFP y de los NFP;
    2. intersecciones entre sus fronteras;
    3. intersecciones con el frente vertical de la
       solución construida hasta el momento.

    Las coordenadas se deduplican durante la generación.
    """

    boundaries = [
        geometry_boundary(ifp_geometry)
    ]

    boundaries.extend(
        geometry_boundary(nfp)
        for nfp in forbidden_nfps
    )

    boundary_bounds = [
        boundary.bounds
        for boundary in boundaries
    ]

    unique_coordinates: dict[
        tuple[float, float],
        None,
    ] = {}

    def add_coordinates(
        geometry: BaseGeometry,
    ) -> None:

        coordinates = (
            extract_coordinates_from_geometry(
                geometry
            )
        )

        for x, y in coordinates:

            key = (
                round(x, decimal_places),
                round(y, decimal_places),
            )

            unique_coordinates.setdefault(
                key,
                None,
            )

    # Vértices de todas las fronteras.
    for boundary in boundaries:
        add_coordinates(boundary)

    # Intersecciones entre las fronteras.
    for first_index in range(
        len(boundaries)
    ):
        for second_index in range(
            first_index + 1,
            len(boundaries),
        ):

            if not _bounds_overlap(
                boundary_bounds[first_index],
                boundary_bounds[second_index],
            ):
                continue

            intersection = (
                boundaries[first_index]
                .intersection(
                    boundaries[second_index]
                )
            )

            add_coordinates(intersection)

    # --------------------------------------------------
    # Candidatos sobre el frente actual del layout
    # --------------------------------------------------

    if front_reference_x is not None:

        (
            ifp_min_x,
            ifp_min_y,
            ifp_max_x,
            ifp_max_y,
        ) = ifp_geometry.bounds

        if (
            ifp_min_x
            <= front_reference_x
            <= ifp_max_x
        ):

            front_line = LineString(
                [
                    (
                        front_reference_x,
                        ifp_min_y,
                    ),
                    (
                        front_reference_x,
                        ifp_max_y,
                    ),
                ]
            )

            # Extremos factibles del frente dentro del IFP.
            add_coordinates(
                front_line.intersection(
                    ifp_geometry
                )
            )

            # Puntos donde el frente toca cada NFP.
            for boundary in boundaries[1:]:

                if not _bounds_overlap(
                    front_line.bounds,
                    boundary.bounds,
                ):
                    continue

                intersection = (
                    front_line.intersection(
                        boundary
                    )
                )

                add_coordinates(intersection)

    return list(unique_coordinates)



def _candidate_is_allowed(
    point: Point,
    point_x: float,
    point_y: float,
    ifp_geometry: BaseGeometry,
    ifp_bounds: Bounds,
    forbidden_nfp_data: list[
        tuple[
            BaseGeometry,
            Bounds,
            bool,
        ]
    ],
) -> bool:
    """
    Determina si una posición candidata puede utilizarse.

    Las coordenadas del punto se reciben ya extraídas
    para evitar accesos repetidos a Point.x y Point.y.
    """

    # Filtro rápido contra la bounding box del IFP.
    if not _coordinates_inside_bounds(
        point_x,
        point_y,
        ifp_bounds,
    ):
        return False

    # Comprobación geométrica exacta del IFP.
    if not ifp_geometry.covers(point):
        return False

    for (
        nfp_geometry,
        nfp_bounds,
        has_area,
    ) in forbidden_nfp_data:

        # Los NFP degenerados no poseen interior
        # bidimensional.
        if not has_area:
            continue

        # Filtro numérico barato.
        if not _coordinates_inside_bounds(
            point_x,
            point_y,
            nfp_bounds,
        ):
            continue

        # Solo llegamos a Shapely si el punto puede
        # encontrarse realmente dentro del NFP.
        if point_is_forbidden_by_nfp(
            point,
            nfp_geometry,
        ):
            return False

    return True



def _placement_score(
    candidate_geometry: BaseGeometry,
    previous_used_length: float,
) -> tuple[float, float, float]:
    """
    Define el criterio determinístico utilizado para
    elegir entre posiciones candidatas válidas.

    Prioridades:

    1. minimizar la longitud total utilizada;
    2. colocar la pieza lo más a la izquierda posible;
    3. usar la menor coordenada vertical como desempate.

    El tercer criterio solo actúa como desempate.
    """

    min_x, min_y, max_x, _ = (
        candidate_geometry.bounds
    )

    new_used_length = max(
        previous_used_length,
        max_x,
    )

    return (
        new_used_length,
        min_x,
        min_y,
    )


def place_next_piece(
    problem: NestingProblem,
    piece_instance: PieceInstance,
    angle: int,
    previous_placements: list[Placement],
) -> Placement:
    """
    Coloca una nueva pieza de forma determinística.

    El orden de las piezas y su orientación vienen dados
    desde afuera. El decoder decide dónde ubicarla.

    Para generar posiciones candidatas utiliza:
    - IFP;
    - NFP respecto de las piezas previamente colocadas;
    - el frente actual del layout.

    Finalmente valida cada candidato directamente con
    Shapely y selecciona el que minimiza la longitud usada.
    """

    polygon_id = piece_instance.polygon_id

    # --------------------------------------------------
    # 1. Validar orientación
    # --------------------------------------------------

    if angle not in piece_instance.allowed_orientations:
        raise ValueError(
            f"La orientación {angle}° no está permitida "
            f"para la instancia "
            f"{piece_instance.instance_id}."
        )

    # --------------------------------------------------
    # 2. Obtener IFP de la pieza
    # --------------------------------------------------

    ifp_geometry = get_ifp_geometry(
        problem=problem,
        piece_polygon_id=polygon_id,
        piece_angle=angle,
    )

    ifp_bounds = ifp_geometry.bounds

    # --------------------------------------------------
    # 3. Construir NFP absolutos respecto de todas
    #    las piezas previamente colocadas
    # --------------------------------------------------

    forbidden_nfps: list[BaseGeometry] = []

    for static_placement in previous_placements:

        absolute_nfp = get_absolute_nfp(
            problem=problem,
            static_polygon_id=(
                static_placement.polygon_id
            ),
            static_angle=(
                static_placement.angle
            ),
            static_reference_x=(
                static_placement.reference_x
            ),
            static_reference_y=(
                static_placement.reference_y
            ),
            orbiting_polygon_id=polygon_id,
            orbiting_angle=angle,
        )

        forbidden_nfps.append(
            absolute_nfp
        )

    # Información precalculada de los NFP para
    # acelerar el filtrado de candidatos.
    forbidden_nfp_data = [
        (
            nfp_geometry,
            nfp_geometry.bounds,
            nfp_geometry.geom_type
            in {"Polygon", "MultiPolygon"},
        )
        for nfp_geometry in forbidden_nfps
    ]

    # --------------------------------------------------
    # 4. Geometrías ya colocadas
    # --------------------------------------------------

    placed_geometries = [
        placement.geometry
        for placement in previous_placements
    ]

    placed_bounds = [
        geometry.bounds
        for geometry in placed_geometries
    ]

    previous_used_length = calculate_used_length(
        placed_geometries
    )

    # --------------------------------------------------
    # 5. Calcular el frente actual del layout
    # --------------------------------------------------

    oriented_piece = get_oriented_piece(
        problem=problem,
        polygon_id=polygon_id,
        angle=angle,
    )

    piece_min_x = oriented_piece.bounds[0]

    # La referencia de la pieza no necesariamente
    # coincide con su extremo izquierdo.
    #
    # Elegimos la coordenada de referencia necesaria
    # para que el extremo izquierdo de la pieza coincida
    # con la longitud actualmente utilizada.
    front_reference_x = (
        previous_used_length
        - piece_min_x
    )

    # --------------------------------------------------
    # 6. Generar posiciones candidatas
    # --------------------------------------------------

    candidate_points = generate_candidate_points(
        ifp_geometry=ifp_geometry,
        forbidden_nfps=forbidden_nfps,
        front_reference_x=front_reference_x,
    )

    # --------------------------------------------------
    # 7. Evaluar candidatos
    # --------------------------------------------------

    valid_candidates = []

    for candidate_x, candidate_y in candidate_points:

        candidate_point = Point(
            candidate_x,
            candidate_y,
        )

        # Primer filtro utilizando IFP y NFP.
        if not _candidate_is_allowed(
            point=candidate_point,
            point_x=candidate_x,
            point_y=candidate_y,
            ifp_geometry=ifp_geometry,
            ifp_bounds=ifp_bounds,
            forbidden_nfp_data=forbidden_nfp_data,
        ):
            continue

        # Construimos la pieza en la posición candidata.
        candidate_geometry = place_piece(
            problem=problem,
            polygon_id=polygon_id,
            angle=angle,
            reference_x=candidate_x,
            reference_y=candidate_y,
        )

        # Validación geométrica final.
        if not is_valid_piece_placement(
            candidate_piece=candidate_geometry,
            board_geometry=problem.board_geometry,
            placed_geometries=placed_geometries,
            placed_bounds=placed_bounds,
        ):
            continue

        # Evaluamos el candidato.
        score = _placement_score(
            candidate_geometry=candidate_geometry,
            previous_used_length=previous_used_length,
        )

        valid_candidates.append(
            (
                score,
                candidate_point,
                candidate_geometry,
            )
        )

    # --------------------------------------------------
    # 8. Verificar que exista al menos una solución
    # --------------------------------------------------

    if not valid_candidates:
        raise RuntimeError(
            "No se encontró una posición válida para "
            f"la instancia "
            f"{piece_instance.instance_id} "
            f"({polygon_id}, {angle}°)."
        )

    # --------------------------------------------------
    # 9. Elegir el mejor candidato
    # --------------------------------------------------

    best_score, best_point, best_geometry = min(
        valid_candidates,
        key=lambda candidate: candidate[0],
    )

    # --------------------------------------------------
    # 10. Devolver colocación
    # --------------------------------------------------

    return Placement(
        instance_id=piece_instance.instance_id,
        piece_id=piece_instance.piece_id,
        polygon_id=polygon_id,
        angle=angle,
        reference_x=float(best_point.x),
        reference_y=float(best_point.y),
        geometry=best_geometry,
    )


def decode_solution(
    problem: NestingProblem,
    order: list[int],
    orientations: list[int],
) -> DecodeResult:
    """
    Decodifica una solución completa.

    Parámetros
    ----------
    order:
        Permutación de los instance_id.

    orientations:
        Lista indexada por instance_id. Para cada pieza
        contiene el ángulo que debe utilizarse.

    Ejemplo:
        order = [2, 0, 1]
        orientations = [0, 180, 0]

    implica:

        primero instancia 2 a 0°
        luego instancia 0 a 0°
        luego instancia 1 a 180°
    """

    n_pieces = len(problem.piece_instances)

    if len(order) == 0:
        return DecodeResult(
            placements=[],
            used_length=0.0,
            is_valid=True,
        )

    if len(orientations) != n_pieces:
        raise ValueError(
            "orientations debe contener una orientación "
            "para cada instancia del problema."
        )

    if len(order) != len(set(order)):
        raise ValueError(
            "El orden contiene instancias duplicadas."
        )

    valid_instance_ids = set(
        range(n_pieces)
    )

    if not set(order).issubset(
        valid_instance_ids
    ):
        raise ValueError(
            "El orden contiene instance_id inválidos."
        )

    placements: list[Placement] = []

    for instance_id in order:
        piece_instance = (
            problem.piece_instances[instance_id]
        )

        angle = int(
            orientations[instance_id]
        )

        placement = place_next_piece(
            problem=problem,
            piece_instance=piece_instance,
            angle=angle,
            previous_placements=placements,
        )

        placements.append(
            placement
        )

    used_length = calculate_used_length(
        [
            placement.geometry
            for placement in placements
        ]
    )

    return DecodeResult(
        placements=placements,
        used_length=used_length,
        is_valid=True,
    )