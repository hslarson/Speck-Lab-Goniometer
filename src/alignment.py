from components.spectrometer import *
from components.constants import *
from components.motors import *

import numpy as np


# Altitude samples for z alignment
ALTITUDE_SAMPLES = [0, 10, 20, 30, 40, 50, 60]


def align_sample_xy_grid(
        spectrometer,
        x_stage: ZaberLinearStage, 
        y_stage: ZaberLinearStage, 
        x_points, y_points,
        recursion_limit,
        recursion_count=0
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
            mean_intensity = np.mean(data[:, 1]) # TODO: restrict wavelength range?

            # Save sample
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
        recursion_limit,
        recursion_count+1
    )



def align_sample_gradient_ascent(
        spectrometer,
        x_stage, y_stage,
        init_step=1,
        min_step=0.001
    ):
    """Align LED to fiber by hill climbing with adaptive step size"""

    def measure(x, y):
        x_stage.set_position(x)
        y_stage.set_position(y)
        data = capture_spectrum(spectrometer)
        return np.sum(np.abs(data[:, 1]))

    # Initial position
    x = x_stage.get_position()
    y = y_stage.get_position()
    step = init_step

    while step >= min_step:
        # 8 surrounding positions
        directions = [
            (0, step),     # N
            (step, step),  # NE
            (step, 0),     # E
            (step, -step), # SE
            (0, -step),    # S
            (-step, -step),# SW
            (-step, 0),    # W
            (-step, step)  # NW
        ]

        # Measure center
        best_score = measure(x, y)
        best_pos = (x, y)

        # Measure neighbors
        for dx, dy in directions:
            x_new, y_new = x + dx, y + dy
            score = measure(x_new, y_new)
            if score > best_score:
                best_score = score
                best_pos = (x_new, y_new)

        # If we find a better neighbor, move there
        if best_pos != (x, y):
            print(f"Moving to better point at step {step:.4f}: ({best_pos[0]:.4f}, {best_pos[1]:.4f}), L1 = {best_score:.2f}")
            x, y = best_pos
        
        # If the center is the best, lower the search radius and repeat
        else:
            step *= 0.5
            print(f"No improvement at step {step*2:.4f}, reducing step to {step:.4f}")

    # Final position
    x_stage.set_position(x)
    y_stage.set_position(y)


def get_pointing_error(
    spectrometer,
    x_stage: ZaberLinearStage,
    y_stage: ZaberLinearStage,
    z_stage: ZaberLinearStage,
    num_points
):
    """
    Laterally align sample at multiple z positions.
    Returns linear fit results for x and y.
    """

    # Initialize samples
    sample_points = np.linspace(0, 50, num_points) # TODO: shouldn't hard code this
    samples = np.zeros((num_points, 2))
    
    # Align sample at each z point
    for iz, z in enumerate(sample_points):
        z_stage.set_position(z)

        x_points = np.linspace(20, 40, 5)
        y_points = np.linspace(30, 50, 5)
        x_mean, y_mean = align_sample_xy(spectrometer, x_stage, y_stage, x_points, y_points, 8)
        samples[iz,:] = [x_mean, y_mean]
    
    # Compute pointing error functions x(z), y(z)
    m_x, b_x = np.polyfit(sample_points, samples[:,0], 1)
    m_y, b_y = np.polyfit(sample_points, samples[:,1], 1)

    # Check R^2
    x_pred = m_x*sample_points+b_x
    ss_res = np.sum((samples[:,0]-x_pred)**2)
    ss_tot = np.sum((samples[:,0]-np.mean(samples[:,0]))**2)
    r_squared = 1 - (ss_res/ss_tot)
    print(f"z(x) = {m_x:.3f}x + {b_x}. R-Squared={r_squared:.3f}")

    y_pred = m_y*sample_points+b_y
    ss_res = np.sum((samples[:,1]-y_pred)**2)
    ss_tot = np.sum((samples[:,1]-np.mean(samples[:,1]))**2)
    r_squared = 1 - (ss_res/ss_tot)
    print(f"z(y) = {m_y:.3f}x + {b_y}. R-Squared={r_squared:.3f}")

    return m_x, b_x, m_y, b_y


def align_sample_z(
        spectrometer,
        x_stage: ZaberLinearStage,
        y_stage: ZaberLinearStage,
        z_stage: ZaberLinearStage,
        altitude_stage: ZaberRotaryStage,
        z_points,
        m_x, b_x,
        m_y, b_y,
        recursion_limit,
        recursion_count=0
    ):
    
    # Check recursion depth. Stop recursion if needed
    if recursion_count > recursion_limit:
        # Compute best estimate
        z_avg = np.mean(z_points)

        # Set final position to best estimate
        z_stage.set_position(z_avg)

        return z_avg
    
    # Initialize sample matrix
    samples = np.zeros((len(z_points), len(ALTITUDE_SAMPLES)))

    # Debug output
    print("-"*30)
    print(f"Recursion Depth = {recursion_count}")
    print(f"Z Search Limits: [{min(z_points):.3f}, {max(z_points):.3f}] ({len(z_points)} Points)")

    # Do grid search
    for iz, z in enumerate(z_points):
        # Move stage to z position
        z_stage.set_position(z)

        # Re-align xy using linear fit parameters
        x_stage.set_position(m_x*z+b_x)
        y_stage.set_position(m_y*z+b_y)

        # Sample different angles
        for ialt, alt in enumerate(ALTITUDE_SAMPLES):
            altitude_stage.set_angle(alt)

            # Collect samples
            data = capture_spectrum(spectrometer)
            mean_intensity = np.mean(data[:, 1]) # TODO: restrict wavelength range?

            # Save sample
            samples[iz, ialt] = mean_intensity

    # Print samples
    np.set_printoptions(precision=3, suppress=True)  # 3 decimal places, no scientific notation
    print(samples)

    # Normalize and integrate samples
    row_maxes = np.max(samples, axis=1, keepdims=True)
    normalized = samples / row_maxes
    row_sums = np.sum(normalized, axis=1)

    # Find maximum sample value and its indices
    max_idx = np.argmax(row_sums)
    print(f"Best sample: {z_points[max_idx]}")

    # Define new search limits
    if (max_idx-1 < 0) or (max_idx+1 >= len(z_points)):
        print("Warning: Best y sample was on the edge of the search grid")
    min_idx = max(max_idx-1, 0)
    max_idx = min(max_idx+1, len(z_points)-1)
    new_z_points = np.linspace(z_points[min_idx], z_points[max_idx], len(z_points))

    # Recursive call
    return align_sample_z(
        spectrometer,
        x_stage,
        y_stage,
        z_stage,
        altitude_stage,
        new_z_points,
        m_x, b_x,
        m_y, b_y,
        recursion_limit,
        recursion_count+1
    )



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
    azimuth_stage.home()
    altitude_stage.home()
    x_stage.home()
    y_stage.home()
    z_stage.home()

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
        max_speed = 20,
        max_accel = 15,
    )

    y_stage.configure(
        limit_min = 0,
        limit_max = 50,
        max_speed = 20,
        max_accel = 15,
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
        int_time_ms=5,
        averages=128
    )

    # Take dark spectrum
    capture_dark_spectrum(spec)

    x, y = align_sample_gradient_ascent(spec, x_stage, y_stage)

    # # Compute pointing functions
    # m_x, b_x, m_y, b_y = get_pointing_error(spec, x_stage, y_stage, z_stage, 3)

    # # Do Z optimization
    # z_points = np.linspace(30, 40, 5)
    # align_sample_z(
    #     spec, 
    #     x_stage,
    #     y_stage,
    #     z_stage,
    #     altitude_stage, 
    #     z_points,
    #     m_x, b_x,
    #     m_y, b_y,
    #     5
    # )
