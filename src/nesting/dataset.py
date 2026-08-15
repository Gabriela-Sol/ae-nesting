# Leer shirts.xml, piezas, tablero, NFP, IFP, crear las 99 instancias

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

from shapely.geometry import Polygon, LineString, Point
from shapely.geometry.base import BaseGeometry


NS = {
    "n": "http://www.fe.up.pt/~esicup/nesting.xsd"
}


@dataclass(frozen=True)
class PieceType:
    """
    Define uno de los tipos de piezas del problema.
    """

    piece_id: str
    polygon_id: str
    quantity: int
    orientations: tuple[int, ...]


@dataclass(frozen=True)
class PieceInstance:
    """
    Representa una copia individual de un tipo de pieza.
    """

    instance_id: int
    piece_id: str
    polygon_id: str
    copy_number: int
    allowed_orientations: tuple[int, ...]


@dataclass
class NestingProblem:
    """
    Contiene toda la información necesaria para resolver
    una instancia de nesting.
    """

    name: str

    board_polygon_id: str
    board_geometry: BaseGeometry

    piece_types: list[PieceType]
    piece_instances: list[PieceInstance]

    geometries: dict[str, BaseGeometry]

    nfp_lookup: dict[
        tuple[str, int, str, int],
        str,
    ]

    ifp_lookup: dict[
        tuple[str, str, int],
        str,
    ]


def _local_name(tag: str) -> str:
    """Elimina el namespace de una etiqueta XML."""

    return tag.split("}")[-1]


def _polygon_element_to_vertices(
    polygon_element: ET.Element,
) -> list[tuple[float, float]]:
    """
    Reconstruye los vértices de una geometría almacenada
    como segmentos en el XML.
    """

    segments = polygon_element.findall(
        "n:lines/n:segment",
        NS,
    )

    ordered_segments = sorted(
        segments,
        key=lambda segment: int(segment.attrib["n"]),
    )

    return [
        (
            float(segment.attrib["x0"]),
            float(segment.attrib["y0"]),
        )
        for segment in ordered_segments
    ]


def _vertices_to_geometry(
    vertices: list[tuple[float, float]],
) -> BaseGeometry:
    """
    Construye el objeto Shapely correspondiente.

    Algunos NFP del dataset son degenerados y se
    representan mediante líneas en lugar de polígonos.
    """

    if len(vertices) >= 3:
        return Polygon(vertices)

    if len(vertices) == 2:
        return LineString(vertices)

    if len(vertices) == 1:
        return Point(vertices[0])

    raise ValueError(
        "No es posible construir una geometría "
        "sin coordenadas."
    )


def _find_descendant(
    element: ET.Element,
    target_name: str,
) -> ET.Element | None:
    """
    Busca un descendiente ignorando el namespace.
    """

    for descendant in element.iter():
        if _local_name(descendant.tag) == target_name:
            return descendant

    return None


def _parse_angle(
    element: ET.Element,
) -> int:
    """
    Convierte el atributo angle a entero.
    """

    return int(
        round(
            float(
                element.attrib.get("angle", 0)
            )
        )
    )


def _get_result_geometry_id(
    relation_element: ET.Element,
) -> str:
    """
    Recupera la geometría resultante de una relación
    NFP o IFP.
    """

    resulting_element = _find_descendant(
        relation_element,
        "resultingPolygon",
    )

    if resulting_element is not None:
        geometry_id = resulting_element.attrib.get(
            "idPolygon"
        )

        if geometry_id is not None:
            return geometry_id

    geometry_id = relation_element.attrib.get(
        "idPolygon"
    )

    if geometry_id is not None:
        return geometry_id

    raise ValueError(
        "No se encontró la geometría resultante "
        "de una relación NFP/IFP."
    )



## lectura de geometrías 
def _load_geometries(
    root: ET.Element,
) -> dict[str, BaseGeometry]:
    """
    Lee todas las geometrías del XML:

    - tablero;
    - piezas;
    - NFP;
    - IFP.
    """

    geometries = {}

    polygon_elements = root.findall(
        "n:polygons/n:polygon",
        NS,
    )

    for polygon_element in polygon_elements:
        geometry_id = polygon_element.attrib["id"]

        vertices = _polygon_element_to_vertices(
            polygon_element
        )

        geometries[geometry_id] = (
            _vertices_to_geometry(vertices)
        )

    return geometries


def _load_piece_types(
    root: ET.Element,
) -> list[PieceType]:
    """
    Lee los tipos de piezas, cantidades,
    geometrías y orientaciones permitidas.
    """

    lot = root.find(
        "n:problem/n:lot",
        NS,
    )

    if lot is None:
        raise ValueError(
            "No se encontró el lote de piezas."
        )

    piece_types = []

    for piece_element in lot.findall(
        "n:piece",
        NS,
    ):
        orientation_elements = (
            piece_element.findall(
                "n:orientation/n:enumeration",
                NS,
            )
        )

        orientations = tuple(
            _parse_angle(element)
            for element in orientation_elements
        )

        component = piece_element.find(
            "n:component",
            NS,
        )

        if component is None:
            raise ValueError(
                "Una pieza no contiene component."
            )

        piece_types.append(
            PieceType(
                piece_id=piece_element.attrib["id"],
                polygon_id=component.attrib[
                    "idPolygon"
                ],
                quantity=int(
                    piece_element.attrib["quantity"]
                ),
                orientations=orientations,
            )
        )

    return piece_types

## expansión a 99 piezas 
def _create_piece_instances(
    piece_types: list[PieceType],
) -> list[PieceInstance]:
    """
    Expande los ocho tipos del dataset en las
    99 piezas físicas que deben colocarse.
    """

    instances = []

    instance_id = 0

    for piece_type in piece_types:
        for copy_number in range(
            1,
            piece_type.quantity + 1,
        ):
            instances.append(
                PieceInstance(
                    instance_id=instance_id,
                    piece_id=piece_type.piece_id,
                    polygon_id=piece_type.polygon_id,
                    copy_number=copy_number,
                    allowed_orientations=(
                        piece_type.orientations
                    ),
                )
            )

            instance_id += 1

    return instances


## leer NFPs
def _load_nfp_lookup(
    root: ET.Element,
) -> dict[tuple[str, int, str, int], str]:
    """
    Crea una tabla de consulta:

    (pieza fija,
     orientación fija,
     pieza móvil,
     orientación móvil)

    -> id del NFP
    """

    lookup = {}

    nfps_section = root.find(
        "n:nfps",
        NS,
    )

    if nfps_section is None:
        raise ValueError(
            "No se encontró la sección NFP."
        )

    for relation in nfps_section:
        if _local_name(relation.tag) != "nfp":
            continue

        static_element = _find_descendant(
            relation,
            "staticPolygon",
        )

        orbiting_element = _find_descendant(
            relation,
            "orbitingPolygon",
        )

        if (
            static_element is None
            or orbiting_element is None
        ):
            raise ValueError(
                "Relación NFP incompleta."
            )

        key = (
            static_element.attrib["idPolygon"],
            _parse_angle(static_element),
            orbiting_element.attrib["idPolygon"],
            _parse_angle(orbiting_element),
        )

        if key in lookup:
            raise ValueError(
                f"Relación NFP duplicada: {key}"
            )

        lookup[key] = _get_result_geometry_id(
            relation
        )

    return lookup


def _load_ifp_lookup(
    root: ET.Element,
) -> dict[tuple[str, str, int], str]:
    """
    Crea una tabla:

    (tablero, pieza, orientación)
    -> id del IFP
    """

    lookup = {}

    ifps_section = root.find(
        "n:ifps",
        NS,
    )

    if ifps_section is None:
        raise ValueError(
            "No se encontró la sección IFP."
        )

    for relation in ifps_section:
        if _local_name(relation.tag) != "ifp":
            continue

        static_element = _find_descendant(
            relation,
            "staticPolygon",
        )

        orbiting_element = _find_descendant(
            relation,
            "orbitingPolygon",
        )

        if (
            static_element is None
            or orbiting_element is None
        ):
            raise ValueError(
                "Relación IFP incompleta."
            )

        key = (
            static_element.attrib["idPolygon"],
            orbiting_element.attrib["idPolygon"],
            _parse_angle(orbiting_element),
        )

        if key in lookup:
            raise ValueError(
                f"Relación IFP duplicada: {key}"
            )

        lookup[key] = _get_result_geometry_id(
            relation
        )

    return lookup


def load_problem(
    xml_path: str | Path,
) -> NestingProblem:
    """
    Carga completamente una instancia ESICUP
    desde un archivo XML.
    """

    xml_path = Path(xml_path)

    if not xml_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {xml_path}"
        )

    tree = ET.parse(xml_path)
    root = tree.getroot()

    name = root.findtext(
        "n:name",
        namespaces=NS,
    )

    geometries = _load_geometries(root)

    piece_types = _load_piece_types(root)

    piece_instances = _create_piece_instances(
        piece_types
    )

    nfp_lookup = _load_nfp_lookup(root)
    ifp_lookup = _load_ifp_lookup(root)

    board_element = root.find(
        "n:problem/n:boards/n:piece",
        NS,
    )

    if board_element is None:
        raise ValueError(
            "No se encontró el tablero."
        )

    board_component = board_element.find(
        "n:component",
        NS,
    )

    board_polygon_id = (
        board_component.attrib["idPolygon"]
    )

    problem = NestingProblem(
        name=name,
        board_polygon_id=board_polygon_id,
        board_geometry=geometries[
            board_polygon_id
        ],
        piece_types=piece_types,
        piece_instances=piece_instances,
        geometries=geometries,
        nfp_lookup=nfp_lookup,
        ifp_lookup=ifp_lookup,
    )

    return problem