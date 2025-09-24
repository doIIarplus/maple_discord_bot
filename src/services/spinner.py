import os
import random
import math
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Polygon, Circle
from PIL import Image
import io


def ease_out_cubic(t: float) -> float:
    """Easing function for smooth deceleration."""
    return 1 - (1 - t) ** 3


def spin_wheel(outcomes, gif_name="spinner.gif", n_frames=60, spin_rotations=5, title=None):
    """
    Generate a GIF of a spinner wheel that lands on a random outcome.

    :param outcomes: List of possible outcomes (strings or emojis).
    :param gif_name: Filename for the output GIF.
    :param n_frames: Number of animation frames.
    :param spin_rotations: How many full rotations before stopping.
    :param title: Optional title text displayed above the wheel.
    :return: (chosen_outcome, gif_name, full_path_to_gif)
    """
    chosen = random.choice(outcomes)
    n = len(outcomes)
    angle_per_slice = 360 / n
    chosen_idx = outcomes.index(chosen)

    # Center of the chosen slice in matplotlib coordinates
    slice_center_angle = chosen_idx * angle_per_slice + angle_per_slice / 2

    # Pointer is at top (90°), so align the chosen slice center with it
    final_angle = 90 - slice_center_angle

    frames = []
    for i in range(n_frames):
        t = ease_out_cubic(i / (n_frames - 1))
        angle_offset = spin_rotations * 360 * (1 - t) + final_angle

        fig, ax = plt.subplots(figsize=(5, 5), subplot_kw={'aspect': 'equal'})
        colors = plt.cm.hsv([j / n for j in range(n)])

        # Draw slices
        for j, outcome in enumerate(outcomes):
            start = j * angle_per_slice + angle_offset
            end = (j + 1) * angle_per_slice + angle_offset
            wedge = Wedge(
                (0, 0), 1, start, end,
                facecolor=colors[j], edgecolor="black", linewidth=2
            )
            ax.add_patch(wedge)

            # Add text/emojis inside slice
            theta = math.radians((j + 0.5) * angle_per_slice + angle_offset)
            x, y = 0.65 * math.cos(theta), 0.65 * math.sin(theta)
            ax.text(
                x, y, str(outcome),
                ha="center", va="center",
                fontsize=12, fontweight="bold", color="black"
            )

        # Center hub
        hub = Circle((0, 0), 0.1, facecolor="white", edgecolor="black", linewidth=2)
        ax.add_patch(hub)

        # Pointer (downward arrow pointing at wheel)
        pointer = Polygon(
            [[-0.1, 1.3], [0.1, 1.3], [0, 1.1]],
            closed=True, facecolor="red", edgecolor="black", linewidth=2
        )
        ax.add_patch(pointer)

        # Add title if provided
        if title:
            ax.text(0, 1.5, title, ha='center', va='center', fontsize=14, fontweight='bold')

        ax.set_xlim(-1.6, 1.6)
        ax.set_ylim(-1.6, 1.6)
        ax.axis("off")

        # Save frame in memory
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight", pad_inches=0.05)
        plt.close(fig)
        buf.seek(0)
        frames.append(Image.open(buf))

    # Save as GIF
    frames[0].save(
        gif_name,
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0
    )

    # Absolute path of GIF
    full_path = os.path.abspath(gif_name)

    return chosen, gif_name, full_path


# Example usage
if __name__ == "__main__":
    outcomes = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    result, gif_file, _ = spin_wheel(outcomes, title="Spin the Wheel!")
    print(f"Chosen outcome: {result}, GIF saved at {gif_file}")
