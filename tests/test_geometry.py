from pathlib import Path

import pytest
from shapely.geometry import Point

from nesting.dataset import load_problem
from nesting.geometry import (
    calculate_used_length,
    classify_piece_relation,
    deduplicate_points,
    get_ifp_geometry,
    get_oriented_piece,
    get_relative_nfp,
    is_valid_piece_placement,
    place_piece,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

XML_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "shirts.xml"
)


@pytest.fixture(scope="module")
def problem():
    return load_problem(XML_PATH)


def test_rotation_preserves_area(problem):
    piece_0 = get_oriented_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
    )

    piece_180 = get_oriented_piece(
        problem,
        polygon_id="polygon1",
        angle=180,
    )

    assert piece_0.area == pytest.approx(
        piece_180.area
    )


def test_place_piece_bounds(problem):
    piece = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=20,
        reference_y=20,
    )

    assert piece.bounds == pytest.approx(
        (
            18.0,
            20.0,
            27.0,
            27.0,
        )
    )


def test_nfp_inside_means_overlap(problem):
    nfp = get_relative_nfp(
        problem,
        static_polygon_id="polygon1",
        static_angle=0,
        orbiting_polygon_id="polygon1",
        orbiting_angle=0,
    )

    relative_point = nfp.representative_point()

    static_x = 25.0
    static_y = 20.0

    static_piece = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=static_x,
        reference_y=static_y,
    )

    orbiting_piece = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=(
            static_x + relative_point.x
        ),
        reference_y=(
            static_y + relative_point.y
        ),
    )

    assert classify_piece_relation(
        static_piece,
        orbiting_piece,
    ) == "overlap"


def test_nfp_boundary_allows_contact(problem):
    nfp = get_relative_nfp(
        problem,
        static_polygon_id="polygon1",
        static_angle=0,
        orbiting_polygon_id="polygon1",
        orbiting_angle=0,
    )

    boundary_point = (
        nfp.boundary.interpolate(
            0.25,
            normalized=True,
        )
    )

    static_x = 25.0
    static_y = 20.0

    static_piece = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=static_x,
        reference_y=static_y,
    )

    orbiting_piece = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=(
            static_x + boundary_point.x
        ),
        reference_y=(
            static_y + boundary_point.y
        ),
    )

    relation = classify_piece_relation(
        static_piece,
        orbiting_piece,
    )

    assert relation == "contact"


def test_ifp_interior_keeps_piece_inside(problem):
    ifp = get_ifp_geometry(
        problem,
        piece_polygon_id="polygon1",
        piece_angle=0,
    )

    point = ifp.representative_point()

    piece = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=point.x,
        reference_y=point.y,
    )

    assert problem.board_geometry.covers(piece)


def test_invalid_piece_outside_board(problem):
    piece = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=1010,
        reference_y=20,
    )

    assert not is_valid_piece_placement(
        candidate_piece=piece,
        board_geometry=problem.board_geometry,
        placed_geometries=[],
    )


def test_overlapping_placement_is_invalid(problem):
    piece_a = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=20,
        reference_y=20,
    )

    piece_b = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=20,
        reference_y=20,
    )

    assert not is_valid_piece_placement(
        candidate_piece=piece_b,
        board_geometry=problem.board_geometry,
        placed_geometries=[piece_a],
    )


def test_deduplicate_points():
    points = [
        Point(1, 2),
        Point(1, 2),
        Point(1.00000000001, 2),
        Point(3, 4),
    ]

    unique_points = deduplicate_points(
        points
    )

    assert len(unique_points) == 2


def test_used_length(problem):
    piece_a = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=20,
        reference_y=20,
    )

    piece_b = place_piece(
        problem,
        polygon_id="polygon1",
        angle=0,
        reference_x=40,
        reference_y=20,
    )

    used_length = calculate_used_length(
        [piece_a, piece_b]
    )

    assert used_length == pytest.approx(47.0)