# Rotar, trasladar, leer geometrías, NFP absoluto, validaciones
from __future__ import annotations

from shapely.affinity import rotate, translate
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from nesting.dataset import NestingProblem


GEOMETRY_TOLERANCE = 1e-8


def _get_allowed_orientations(
    problem: NestingProblem,
    polygon_id: str,
) -> tuple[int, ...]:
    """
    Devuelve las orientaciones permitidas para un tipo
    de pieza a partir de su polygon_id.
    """

    for piece_type in problem.piece_types:
        if piece_type.polygon_id == polygon_id:
            return piece_type.orientations

    raise KeyError(
        f"No se encontró una pieza asociada a {polygon_id}."
    )


def get_oriented_piece(
    problem: NestingProblem,
    polygon_id: str,
    angle: int,
) -> BaseGeometry:
    """
    Recupera una pieza del problema y aplica la orientación
    indicada alrededor de su punto de referencia (0, 0).

    La geometría NO se normaliza ni se traslada, porque los
    NFP e IFP del XML utilizan las coordenadas originales.
    """

    if polygon_id not in problem.geometries:
        raise KeyError(
            f"No existe la geometría {polygon_id}."
        )

    allowed_orientations = _get_allowed_orientations(
        problem,
        polygon_id,
    )

    if angle not in allowed_orientations:
        raise ValueError(
            f"La orientación {angle}° no está permitida "
            f"para {polygon_id}. "
            f"Orientaciones válidas: {allowed_orientations}"
        )

    geometry = problem.geometries[polygon_id]

    if geometry.geom_type != "Polygon":
        raise TypeError(
            f"{polygon_id} debería ser un Polygon, "
            f"pero es {geometry.geom_type}."
        )

    return rotate(
        geometry,
        angle=angle,
        origin=(0, 0),
        use_radians=False,
    )


def place_piece(
    problem: NestingProblem,
    polygon_id: str,
    angle: int,
    reference_x: float,
    reference_y: float,
) -> BaseGeometry:
    """
    Orienta una pieza y traslada su punto de referencia
    desde (0, 0) hasta (reference_x, reference_y).
    """

    oriented_piece = get_oriented_piece(
        problem=problem,
        polygon_id=polygon_id,
        angle=angle,
    )

    return translate(
        oriented_piece,
        xoff=reference_x,
        yoff=reference_y,
    )


def get_ifp_geometry(
    problem: NestingProblem,
    piece_polygon_id: str,
    piece_angle: int,
) -> BaseGeometry:
    """
    Recupera el Inner-Fit Polygon (IFP) correspondiente
    a una pieza y una orientación.

    El IFP representa las posiciones permitidas para el
    punto de referencia de la pieza dentro del tablero.
    """

    key = (
        problem.board_polygon_id,
        piece_polygon_id,
        int(piece_angle),
    )

    if key not in problem.ifp_lookup:
        raise KeyError(
            "No existe un IFP para:\n"
            f"  tablero: {problem.board_polygon_id}\n"
            f"  pieza: {piece_polygon_id}\n"
            f"  orientación: {piece_angle}°"
        )

    geometry_id = problem.ifp_lookup[key]

    return problem.geometries[geometry_id]


def get_relative_nfp(
    problem: NestingProblem,
    static_polygon_id: str,
    static_angle: int,
    orbiting_polygon_id: str,
    orbiting_angle: int,
) -> BaseGeometry:
    """
    Recupera el No-Fit Polygon (NFP) relativo entre
    una pieza fija y una pieza móvil.

    La geometría se encuentra expresada respecto del
    punto de referencia de la pieza fija.
    """

    key = (
        static_polygon_id,
        int(static_angle),
        orbiting_polygon_id,
        int(orbiting_angle),
    )

    if key not in problem.nfp_lookup:
        raise KeyError(
            "No existe un NFP para:\n"
            f"  fija: {static_polygon_id} "
            f"a {static_angle}°\n"
            f"  móvil: {orbiting_polygon_id} "
            f"a {orbiting_angle}°"
        )

    geometry_id = problem.nfp_lookup[key]

    return problem.geometries[geometry_id]


def get_absolute_nfp(
    problem: NestingProblem,
    static_polygon_id: str,
    static_angle: int,
    static_reference_x: float,
    static_reference_y: float,
    orbiting_polygon_id: str,
    orbiting_angle: int,
) -> BaseGeometry:
    """
    Obtiene el NFP correspondiente a dos piezas y lo
    traslada hasta la posición real de la pieza fija.
    """

    relative_nfp = get_relative_nfp(
        problem=problem,
        static_polygon_id=static_polygon_id,
        static_angle=static_angle,
        orbiting_polygon_id=orbiting_polygon_id,
        orbiting_angle=orbiting_angle,
    )

    return translate(
        relative_nfp,
        xoff=static_reference_x,
        yoff=static_reference_y,
    )


def geometry_boundary(
    geometry: BaseGeometry,
) -> BaseGeometry:
    """
    Devuelve la frontera útil de una geometría.

    - Para Polygon/MultiPolygon se utiliza .boundary.
    - Para LineString, MultiLineString o Point se utiliza
      la propia geometría.
    """

    if geometry.geom_type in {
        "Polygon",
        "MultiPolygon",
    }:
        return geometry.boundary

    return geometry


def extract_points_from_geometry(
    geometry: BaseGeometry,
) -> list[Point]:
    """
    Extrae puntos candidatos desde distintos tipos de
    geometrías Shapely.

    Se utiliza para obtener vértices e intersecciones
    que luego funcionarán como posiciones candidatas.
    """

    if geometry.is_empty:
        return []

    geometry_type = geometry.geom_type

    if geometry_type == "Point":
        return [geometry]

    if geometry_type == "MultiPoint":
        return list(geometry.geoms)

    if geometry_type in {
        "LineString",
        "LinearRing",
    }:
        return [
            Point(x, y)
            for x, y in geometry.coords
        ]

    if geometry_type == "Polygon":
        points = [
            Point(x, y)
            for x, y in list(
                geometry.exterior.coords
            )[:-1]
        ]

        for interior_ring in geometry.interiors:
            points.extend(
                Point(x, y)
                for x, y in list(
                    interior_ring.coords
                )[:-1]
            )

        return points

    if geometry_type in {
        "MultiLineString",
        "MultiPolygon",
        "GeometryCollection",
    }:
        points = []

        for subgeometry in geometry.geoms:
            points.extend(
                extract_points_from_geometry(
                    subgeometry
                )
            )

        return points

    raise TypeError(
        f"Tipo geométrico no soportado: "
        f"{geometry_type}"
    )


def deduplicate_points(
    points: list[Point],
    decimal_places: int = 8,
) -> list[Point]:
    """
    Elimina puntos repetidos utilizando coordenadas
    redondeadas para absorber pequeños errores numéricos.
    """

    unique_points: dict[
        tuple[float, float],
        Point,
    ] = {}

    for point in points:
        key = (
            round(point.x, decimal_places),
            round(point.y, decimal_places),
        )

        if key not in unique_points:
            unique_points[key] = Point(
                float(key[0]),
                float(key[1]),
            )

    return list(unique_points.values())


def point_is_forbidden_by_nfp(
    point: Point,
    nfp_geometry: BaseGeometry,
) -> bool:
    """
    Indica si un punto se encuentra estrictamente dentro
    de una región NFP prohibida.

    El borde del NFP se considera permitido porque
    representa contacto sin solapamiento.

    Los NFP degenerados representados como líneas no
    poseen interior bidimensional. Su validez se controla
    posteriormente mediante intersección directa.
    """

    if nfp_geometry.geom_type == "Polygon":
        return nfp_geometry.contains(point)

    if nfp_geometry.geom_type == "MultiPolygon":
        return any(
            polygon.contains(point)
            for polygon in nfp_geometry.geoms
        )

    return False


def classify_piece_relation(
    piece_a: BaseGeometry,
    piece_b: BaseGeometry,
    tolerance: float = GEOMETRY_TOLERANCE,
) -> str:
    """
    Clasifica la relación geométrica entre dos piezas:

    - 'overlap': existe área de solapamiento.
    - 'contact': se tocan pero no se superponen.
    - 'separate': existe distancia positiva.
    """

    intersection_area = piece_a.intersection(
        piece_b
    ).area

    distance = piece_a.distance(piece_b)

    if intersection_area > tolerance:
        return "overlap"

    if distance <= tolerance:
        return "contact"

    return "separate"


def is_valid_piece_placement(
    candidate_piece: BaseGeometry,
    board_geometry: BaseGeometry,
    placed_geometries: list[BaseGeometry],
    tolerance: float = GEOMETRY_TOLERANCE,
) -> bool:
    """
    Verifica que una pieza candidata:

    1. permanezca completamente dentro del tablero;
    2. no se superponga con ninguna pieza ya colocada.

    El contacto entre bordes está permitido.
    """

    if not board_geometry.covers(
        candidate_piece
    ):
        return False

    for placed_geometry in placed_geometries:
        intersection_area = (
            candidate_piece
            .intersection(placed_geometry)
            .area
        )

        if intersection_area > tolerance:
            return False

    return True


def calculate_used_length(
    geometries: list[BaseGeometry],
) -> float:
    """
    Calcula la longitud de tela utilizada como la
    coordenada x máxima alcanzada por las piezas.
    """

    if not geometries:
        return 0.0

    return max(
        geometry.bounds[2]
        for geometry in geometries
    )