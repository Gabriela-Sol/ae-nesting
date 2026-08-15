from pathlib import Path

import pytest

from nesting.dataset import load_problem
from nesting.decoder import (
    decode_solution,
    generate_candidate_points,
    place_next_piece,
)
from nesting.geometry import get_ifp_geometry


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


def test_first_piece_can_be_placed(problem):
    piece_instance = problem.piece_instances[0]

    placement = place_next_piece(
        problem=problem,
        piece_instance=piece_instance,
        angle=0,
        previous_placements=[],
    )

    assert placement.instance_id == 0

    assert problem.board_geometry.covers(
        placement.geometry
    )


def test_first_piece_uses_left_edge(problem):
    piece_instance = problem.piece_instances[0]

    placement = place_next_piece(
        problem=problem,
        piece_instance=piece_instance,
        angle=0,
        previous_placements=[],
    )

    min_x = placement.geometry.bounds[0]

    assert min_x == pytest.approx(
        0.0,
        abs=1e-8,
    )


def test_decode_three_pieces(problem):
    order = [0, 1, 2]

    orientations = [
        0
        for _ in problem.piece_instances
    ]

    result = decode_solution(
        problem=problem,
        order=order,
        orientations=orientations,
    )

    assert result.is_valid
    assert len(result.placements) == 3
    assert result.used_length > 0


def test_three_pieces_do_not_overlap(problem):
    order = [0, 1, 2]

    orientations = [
        0
        for _ in problem.piece_instances
    ]

    result = decode_solution(
        problem=problem,
        order=order,
        orientations=orientations,
    )

    placements = result.placements

    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            intersection_area = (
                placements[i]
                .geometry
                .intersection(
                    placements[j].geometry
                )
                .area
            )

            assert intersection_area <= 1e-8


def test_three_pieces_stay_inside_board(problem):
    order = [0, 1, 2]

    orientations = [
        0
        for _ in problem.piece_instances
    ]

    result = decode_solution(
        problem=problem,
        order=order,
        orientations=orientations,
    )

    for placement in result.placements:
        assert problem.board_geometry.covers(
            placement.geometry
        )


def test_duplicate_order_is_rejected(problem):
    orientations = [
        0
        for _ in problem.piece_instances
    ]

    with pytest.raises(ValueError):
        decode_solution(
            problem=problem,
            order=[0, 0, 1],
            orientations=orientations,
        )


def test_invalid_orientation_is_rejected(problem):
    orientations = [
        0
        for _ in problem.piece_instances
    ]

    orientations[0] = 90

    with pytest.raises(ValueError):
        decode_solution(
            problem=problem,
            order=[0],
            orientations=orientations,
        )



def test_decode_ten_pieces(problem):
    order = list(range(10))

    orientations = [
        0
        for _ in problem.piece_instances
    ]

    result = decode_solution(
        problem=problem,
        order=order,
        orientations=orientations,
    )

    assert result.is_valid
    assert len(result.placements) == 10

    for placement in result.placements:
        assert problem.board_geometry.covers(
            placement.geometry
        )

    for i in range(len(result.placements)):
        for j in range(
            i + 1,
            len(result.placements),
        ):
            overlap_area = (
                result.placements[i]
                .geometry
                .intersection(
                    result.placements[j].geometry
                )
                .area
            )

            assert overlap_area <= 1e-8