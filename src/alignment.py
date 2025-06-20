from components.spectrometer import *
from components.constants import *
from components.motors import *

import numpy as np


# Altitude samples for z alignment
ALTITUDE_SAMPLES = [20, 40, 60]


def align_sample_xy_grid(
        spectrometer,
        x_stage: ZaberLinearStage, 
        y_stage: ZaberLinearStage, 
        x_points, y_points,
        wavelength_mask,
        recursion_limit,
        recursion_count=0,
    ):
    """Laterally align sample using a recursive grid search"""

    # Check recursion depth
    if recursion_count > recursion_limit:
        # Compute search grid center
        x_avg = np.mean(x_points)
        y_avg = np.mean(y_points)

        # Set final position to search grid center
        x_stage.set_position(x_avg)
        y_stage.set_position(y_avg)

        return x_avg, y_avg
    
    # Initialize sample grid
    samples = np.zeros((len(y_points), len(x_points)))

    # Debug output
    print("-"*64)
    print(f"Recursion Depth = {recursion_count}")
    print(f"X Search Limits: [{min(x_points):.3f}, {max(x_points):.3f}] ({len(x_points)} Points)")
    print(f"Y Search Limits: [{min(y_points):.3f}, {max(y_points):.3f}] ({len(y_points)} Points)")

    # Do grid search
    for iy, y in enumerate(y_points):
        y_stage.set_position(y)
        for ix, x in enumerate(x_points):
            x_stage.set_position(x)

            # Collect sample
            data = capture_spectrum(spectrometer)
            mean_intensity = np.mean(data[:, 1] if wavelength_mask is None else data[wavelength_mask, 1])
            samples[iy, ix] = mean_intensity
    
    # Find maximum sample value and its indices
    max_idx = np.unravel_index(np.argmax(samples), samples.shape)
    iy_max, ix_max = max_idx
    print(f"Best sample: ({x_points[ix_max]}, {y_points[iy_max]})")

    # Define new search limits
    if (ix_max-1 < 0) or (ix_max+1 >= len(x_points)):
        print("Warning: Best x sample was on the edge of the search grid")
    ix_min = max(ix_max-1, 0)
    ix_max = min(ix_max+1, len(x_points)-1)

    if (iy_max-1 < 0) or (iy_max+1 >= len(y_points)):
        print("Warning: Best y sample was on the edge of the search grid")
    iy_min = max(iy_max-1, 0)
    iy_max = min(iy_max+1, len(y_points)-1)

    new_x_points = np.linspace(x_points[ix_min], x_points[ix_max], len(x_points))
    new_y_points = np.linspace(y_points[iy_min], y_points[iy_max], len(y_points))

    # Recursive function call
    return align_sample_xy_grid(
        spectrometer,
        x_stage,
        y_stage,
        new_x_points,
        new_y_points,
        wavelength_mask,
        recursion_limit,
        recursion_count+1
    )


def align_sample_xy_greedy(
        spectrometer,
        x_stage, y_stage,
        init_step=1,
        target_step=0.05,
        wavelength_mask=None
    ):
    """Laterally align sample by greedy hill climbing with adaptive step size"""

    def measure(x, y):
        x_stage.set_position(x)
        y_stage.set_position(y)
        data = capture_spectrum(spectrometer)
        return np.sum(data[:, 1] if wavelength_mask is None else data[wavelength_mask, 1])

    # Get initial position
    x = x_stage.get_position()
    y = y_stage.get_position()
    step = init_step

    # Measure center statistics
    readings = [measure(x, y) for _ in range(10)]
    std_dev = np.std(readings)
    best_score = np.mean(readings)

    while step >= target_step:
        # 8 surrounding positions
        directions = [
            (0,      step), # N
            (step,   step), # NE
            (step,   0),    # E
            (step,  -step), # SE
            (0,     -step), # S
            (-step, -step), # SW
            (-step,  0),    # W
            (-step,  step)  # NW
        ]

        # Measure neighbors
        for dx, dy in directions:
            x_new, y_new = x + dx, y + dy
            score = measure(x_new, y_new)

            # If we find a better point, go there immediately
            if score > best_score + 1.5*std_dev:
                print(f"Moving to ({x_new:.4f}, {y_new:.4f}), L1={score}")
                x, y = (x_new, y_new)
                best_score = score
                break
    
        # If the center is the best, lower the search radius and repeat
        else:
            step *= 0.5
            x_stage.set_position(x)
            y_stage.set_position(y)
            print(f"No improvement, reducing step to {step:.4f}")

    # Return final position
    return x, y


def get_pointing_error(
    spectrometer,
    x_stage: ZaberLinearStage,
    y_stage: ZaberLinearStage,
    z_stage: ZaberLinearStage,
    sample_points,
    wavelength_mask=None
):
    """
    Laterally align sample at multiple z positions.
    Returns linear fit results for x and y.
    """

    # Initialize samples
    samples = np.zeros((len(sample_points), 2))
    
    # Align sample at each z point
    for iz, z in enumerate(sample_points):
        print(f"Laterally aligning for z={z:.2f}")
        z_stage.set_position(z)
        x_mean, y_mean = align_sample_xy_greedy(
            spectrometer, 
            x_stage, y_stage, 
            init_step=0.2,
            wavelength_mask=wavelength_mask
        )
        samples[iz,:] = [x_mean, y_mean]
    
    # Compute pointing error functions x(z), y(z)
    m_x, b_x = np.polyfit(sample_points, samples[:,0], 1)
    m_y, b_y = np.polyfit(sample_points, samples[:,1], 1)

    print(sample_points)
    print(samples)

    # Check R^2
    x_pred = m_x*sample_points+b_x
    ss_res = np.sum((samples[:,0]-x_pred)**2)
    ss_tot = np.sum((samples[:,0]-np.mean(samples[:,0]))**2)
    r_squared_x = 1 - (ss_res/ss_tot)
    print(f"x(z) = {m_x:.3f}z + {b_x}. R-Squared={r_squared_x:.3f}")

    y_pred = m_y*sample_points+b_y
    ss_res = np.sum((samples[:,1]-y_pred)**2)
    ss_tot = np.sum((samples[:,1]-np.mean(samples[:,1]))**2)
    r_squared_y = 1 - (ss_res/ss_tot)
    print(f"y(z) = {m_y:.3f}z + {b_y}. R-Squared={r_squared_y:.3f}")

    return m_x, b_x, m_y, b_y, r_squared_x, r_squared_y


def align_sample_z_greedy(
        spectrometer,
        x_stage: ZaberLinearStage,
        y_stage: ZaberLinearStage,
        z_stage: ZaberLinearStage,
        altitude_stage: ZaberRotaryStage,
        m_x, b_x,
        m_y, b_y,
        init_step=1,
        target_step=0.05,
        wavelength_mask=None
    ):
    """Vertically align sample by greedy hill climbing with adaptive step size"""

    def measure(z):
        # Move stage to z position
        z_stage.set_position(z)

        # Re-align xy using linear fit parameters
        x_stage.set_position(m_x*z+b_x)
        y_stage.set_position(m_y*z+b_y)

        # Sample different angles
        score = 0
        for alt in ALTITUDE_SAMPLES:
            altitude_stage.set_angle(alt)
            data = capture_spectrum(spectrometer)
            score += np.sum(data[:, 1] if wavelength_mask is None else data[wavelength_mask, 1]) 
        return score

    # Get initial position
    z = z_stage.get_position()
    step = init_step

    # Measure center
    best_score = measure(z)
    best_z = z

    while step >= target_step:
        # Measure neighbors
        for z_test in (z+step, z-step):
            score = measure(z_test)
            print(f"{z_test} --> {score}")
            if score > best_score:
                best_score = score
                best_z = z_test

        # If we find a better neighbor, move there
        if best_z != z:
            print(f"Moving to ({best_z:.4f}, {best_z:.4f}), L1 = {best_score:.2f}")
            z = best_z
            best_score = measure(z)
        
        # If the center is the best, lower the search radius and repeat
        else:
            step *= 0.5
            print(f"No improvement, reducing step to {step:.4f}")

    # Set final position
    z_stage.set_position(z)
    x_stage.set_position(m_x*z+b_x)
    y_stage.set_position(m_y*z+b_y)
    return z



if __name__ == "__main__":
    # Open USB
    conn = open_zaber_connection()
    
    # Connect to rotary stages
    azimuth_stage  = ZaberRotaryStage(ZABER_AZIMUTH_SERIAL_NUM, conn)
    altitude_stage = ZaberRotaryStage(ZABER_ALTITUDE_SERIAL_NUM, conn)

    # Connect to linear stages
    x_stage = ZaberLinearStage(ZABER_X_SERIAL_NUM, conn)
    y_stage = ZaberLinearStage(ZABER_Y_SERIAL_NUM, conn)
    z_stage = ZaberLinearStage(ZABER_Z_SERIAL_NUM, conn)

    # Home stages
    # azimuth_stage.home()
    # altitude_stage.home()
    # x_stage.home()
    # y_stage.home()
    # z_stage.home()

    # Configure rotary stages
    azimuth_stage.configure(
        angle_offset = ZABER_AZIMUTH_ANGLE_OFFSET,
        limit_min = -90,
        limit_max =  90,
        max_speed = 30,
        max_accel = 5
    )

    altitude_stage.configure(
        angle_offset = ZABER_ALTITUDE_ANGLE_OFFSET,
        limit_min = -90,
        limit_max =  90,
        max_speed = 30,
        max_accel = 5
    )

    # Configure linear stages
    x_stage.configure(
        limit_min = 0,
        limit_max = 50,
        max_speed = 10,
        max_accel = 5,
    )

    y_stage.configure(
        limit_min = 0,
        limit_max = 50,
        max_speed = 10,
        max_accel = 5,
    )

    z_stage.configure(
        limit_min = 0,
        limit_max = 50,
        max_speed = 20,
        max_accel = 15,
    )

    # Set rotary stage positions
    azimuth_stage.set_angle(0)
    altitude_stage.set_angle(0)

    # === Initialize spectrometer ===
    spec = get_spectrometer()
    configure_spectrometer(
        spec,
        int_time_ms=1.2,
        averages=128
    )

    # Take dark spectrum
    capture_dark_spectrum(spec)
    data = capture_spectrum(spec)

    # Define wavelength mask
    WAVELENGTH_MIN = 400
    WAVELENGTH_MAX = 500
    mask = (data[:, 0] >= WAVELENGTH_MIN) & (data[:, 0] <= WAVELENGTH_MAX)
    
    # Align sample in x/y
    sample_points = np.linspace(0, 50, 4)
    m_x, b_x, m_y, b_y, r_sq_x, r_sq_y = get_pointing_error(
        spec, 
        x_stage, y_stage, z_stage, 
        sample_points,
        mask
    )

    # Assert linearity
    # assert (r_sq_x > 0.98) and (r_sq_y > 0.98), "Line fitting failed"

    z_stage.set_position(25)

    # Align sample in z
    align_sample_z_greedy(
        spec,
        x_stage, y_stage, z_stage,
        altitude_stage,
        m_x, b_x,
        m_y, b_y,
        init_step=5,
        wavelength_mask=mask
    )
