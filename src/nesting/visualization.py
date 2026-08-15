from __future__ import annotations

import matplotlib.pyplot as plt

from nesting.decoder import DecodeResult


def plot_layout(
    result: DecodeResult,
    board_width: float = 40.0,
    title: str = "Nesting layout",
    show_reference_points: bool = True,
    show_instance_ids: bool = True,
    margin: float = 2.0,
    figsize: tuple[float, float] = (14, 6),
):
    """
    Visualiza el layout producido por el decoder.

    El eje x representa la longitud utilizada de tela
    y el eje y el ancho fijo del rollo.
    """

    fig, ax = plt.subplots(
        figsize=figsize
    )

    # Área de tela efectivamente utilizada.
    ax.fill(
        [
            0,
            result.used_length,
            result.used_length,
            0,
        ],
        [
            0,
            0,
            board_width,
            board_width,
        ],
        alpha=0.08,
        label="Tela utilizada",
    )

    for placement in result.placements:
        geometry = placement.geometry

        x, y = geometry.exterior.xy

        ax.fill(
            x,
            y,
            alpha=0.45,
        )

        ax.plot(
            x,
            y,
            linewidth=1,
        )

        if show_reference_points:
            ax.scatter(
                placement.reference_x,
                placement.reference_y,
                marker="x",
                s=35,
            )

        if show_instance_ids:
            centroid = geometry.centroid

            ax.text(
                centroid.x,
                centroid.y,
                str(placement.instance_id),
                ha="center",
                va="center",
                fontsize=8,
            )

    # Inicio y final de la longitud utilizada.
    ax.axvline(
        0,
        linewidth=1.5,
    )

    ax.axvline(
        result.used_length,
        linestyle="--",
        linewidth=1.5,
        label=(
            f"Longitud usada = "
            f"{result.used_length:.2f}"
        ),
    )

    ax.axhline(
        0,
        linewidth=1,
    )

    ax.axhline(
        board_width,
        linewidth=1,
    )

    ax.set_xlim(
        -margin,
        result.used_length + margin,
    )

    ax.set_ylim(
        -margin,
        board_width + margin,
    )

    ax.set_xlabel(
        "Longitud de tela"
    )

    ax.set_ylabel(
        "Ancho de tela"
    )

    ax.set_title(title)

    ax.set_aspect("equal")
    ax.grid(alpha=0.2)
    ax.legend()

    # El dataset utiliza origen arriba a la izquierda.
    ax.invert_yaxis()

    plt.tight_layout()

    return fig, ax