"""Small synthetic calculation for workspace navigation and editing practice."""


def solve(tolerance=1e-6):
    residual = 1.0
    iteration = 0
    for iteration in range(1, 25):
        residual *= 0.5
        if residual < tolerance:
            break
    return iteration, residual


if __name__ == "__main__":
    iterations, final_residual = solve()
    print(f"iterations={iterations} residual={final_residual:.3e}")
