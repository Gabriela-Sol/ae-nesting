from pathlib import Path

from nesting.dataset import load_problem


PROJECT_ROOT = Path(__file__).resolve().parents[1]

XML_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "shirts.xml"
)


def test_load_shirts():
    problem = load_problem(XML_PATH)

    assert problem.name == "Shirts"

    assert len(problem.piece_types) == 8
    assert len(problem.piece_instances) == 99

    assert problem.board_polygon_id == "polygon0"

    assert problem.board_geometry.bounds == (
        0.0,
        0.0,
        1000.0,
        40.0,
    )

    assert len(problem.nfp_lookup) > 0
    assert len(problem.ifp_lookup) > 0


def test_all_piece_orientations():
    problem = load_problem(XML_PATH)

    for piece_type in problem.piece_types:
        assert piece_type.orientations == (
            0,
            180,
        )


def test_unique_instance_ids():
    problem = load_problem(XML_PATH)

    instance_ids = [
        piece.instance_id
        for piece in problem.piece_instances
    ]

    assert len(instance_ids) == len(
        set(instance_ids)
    )