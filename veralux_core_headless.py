"""
VeraLux Core Engine — Version headless (sans GUI/PyQt6)
==========================================================
Extrait fidèle de VeraLux_HyperMetric_Stretch.py v1.5.2 (Riccardo Paterniti, GPL-3.0-or-later)
Seule la classe VeraLuxCore et les fonctions de traitement pur sont conservées.
Toute la partie interface (QWidget, QThread, sliders...) a été retirée.

Ce fichier est importé par veralux_stretch_pyscript.py — il ne s'exécute pas seul.
"""

import numpy as np

# =============================================================================
#  PROFILS CAPTEUR (extrait — ajoute d'autres profils si besoin depuis l'original)
# =============================================================================
SENSOR_PROFILES = {
    "Rec.709 (Recommended)": {'weights': (0.2126, 0.7152, 0.0722)},
    "Sony IMX585 (ASI585) - STARVIS 2": {'weights': (0.3431, 0.4822, 0.1747)},
    "Sony IMX662 (ASI662) - STARVIS 2": {'weights': (0.3430, 0.4821, 0.1749)},
    "Sony IMX533 (ASI533)": {'weights': (0.2910, 0.5072, 0.2018)},
    "Sony IMX571 (ASI2600/QHY268)": {'weights': (0.2944, 0.5021, 0.2035)},
    "Sony IMX294 (ASI294)": {'weights': (0.3068, 0.5008, 0.1925)},
}
DEFAULT_PROFILE = "Rec.709 (Recommended)"


class VeraLuxCore:
    _last_linear_expansion_diag = {"pct_low": 0.0, "pct_high": 0.0, "low": 0.0, "high": 0.0}

    @staticmethod
    def normalize_input(img_data):
        img_data = np.nan_to_num(img_data, nan=0.0, posinf=None, neginf=0.0)
        input_dtype = img_data.dtype
        img_float = img_data.astype(np.float32)

        if np.issubdtype(input_dtype, np.integer):
            if input_dtype == np.uint8:
                return img_float / 255.0
            elif input_dtype == np.uint16:
                return img_float / 65535.0
            elif input_dtype == np.int16:
                return img_float / 32767.0
            else:
                return img_float / 4294967295.0
        elif np.issubdtype(input_dtype, np.floating):
            current_max = float(np.max(img_data))
            if current_max <= 1.1:
                return img_float
            if current_max < 100000.0:
                return img_float / 65535.0
            return img_float / 4294967295.0
        return img_float

    @staticmethod
    def calculate_anchor(data_norm):
        if data_norm.ndim == 3 and data_norm.shape[0] == 3:
            floors = []
            stride = max(1, data_norm.size // 500000)
            for c in range(3):
                floors.append(np.percentile(data_norm[c].flatten()[::stride], 0.5))
            anchor = max(0.0, min(floors) - 0.00025)
        elif data_norm.ndim == 2 and data_norm.shape[0] == 3:
            floors = []
            stride = max(1, data_norm.size // 500000)
            for c in range(3):
                floors.append(np.percentile(data_norm[c].flatten()[::stride], 0.5))
            anchor = max(0.0, min(floors) - 0.00025)
        elif data_norm.ndim == 3 and data_norm.shape[0] == 1:
            stride = max(1, data_norm.size // 200000)
            floor = np.percentile(data_norm[0].flatten()[::stride], 0.5)
            anchor = max(0.0, floor - 0.00025)
        else:
            stride = max(1, data_norm.size // 200000)
            floor = np.percentile(data_norm.flatten()[::stride], 0.5)
            anchor = max(0.0, floor - 0.00025)
        return anchor

    @staticmethod
    def calculate_anchor_adaptive(data_norm, weights=None):
        if weights is None:
            weights = (0.2126, 0.7152, 0.0722)

        if data_norm.ndim == 3 and data_norm.shape[0] == 3:
            r_w, g_w, b_w = weights
            base = r_w * data_norm[0] + g_w * data_norm[1] + b_w * data_norm[2]
        elif data_norm.ndim == 2 and data_norm.shape[0] == 3:
            r_w, g_w, b_w = weights
            base = r_w * data_norm[0] + g_w * data_norm[1] + b_w * data_norm[2]
        elif data_norm.ndim == 3 and data_norm.shape[0] == 1:
            base = data_norm[0]
        else:
            base = data_norm

        stride = max(1, base.size // 2000000)
        sample = base.flatten()[::stride]

        hist, bin_edges = np.histogram(sample, bins=65536, range=(0.0, 1.0))
        hist_smooth = np.convolve(hist, np.ones(50) / 50, mode='same')

        search_start = 100
        if np.max(hist_smooth[:search_start]) > 0:
            search_start = 0
        if search_start >= len(hist_smooth):
            search_start = 0

        peak_idx = int(np.argmax(hist_smooth[search_start:]) + search_start)
        peak_val = float(hist_smooth[peak_idx])
        target_val = peak_val * 0.06

        left_side = hist_smooth[:peak_idx]
        candidates = np.where(left_side < target_val)[0]

        if len(candidates) > 0:
            anchor = bin_edges[candidates[-1]]
        else:
            anchor = np.percentile(sample, 0.5)

        return max(0.0, anchor)

    @staticmethod
    def extract_luminance(data_norm, anchor, weights):
        r_w, g_w, b_w = weights
        img_anchored = np.maximum(data_norm - anchor, 0.0)

        if data_norm.ndim == 3 and data_norm.shape[0] == 3:
            L_anchored = r_w * img_anchored[0] + g_w * img_anchored[1] + b_w * img_anchored[2]
        elif data_norm.ndim == 2 and data_norm.shape[0] == 3:
            L_anchored = r_w * img_anchored[0] + g_w * img_anchored[1] + b_w * img_anchored[2]
        elif data_norm.ndim == 3 and data_norm.shape[0] == 1:
            L_anchored = img_anchored[0]
            img_anchored = img_anchored[0]
        else:
            L_anchored = img_anchored

        return L_anchored, img_anchored

    @staticmethod
    def estimate_star_pressure(L_anchored):
        if L_anchored is None or L_anchored.size == 0:
            return 0.0
        stride = max(1, L_anchored.size // 300000)
        sample = L_anchored.flatten()[::stride]
        sample = sample[sample > 1e-7]
        if sample.size < 100:
            return 0.0
        p999 = np.percentile(sample, 99.9)
        p9999 = np.percentile(sample, 99.99)
        bright_frac = np.count_nonzero(sample > p999) / sample.size
        p_term = np.clip(p9999 / (p999 + 1e-9), 1.0, 5.0)
        p_term = (p_term - 1.0) / 4.0
        f_term = np.clip(bright_frac * 200.0, 0.0, 1.0)
        return float(np.clip(0.7 * p_term + 0.3 * f_term, 0.0, 1.0))

    @staticmethod
    def hyperbolic_stretch(data, D, b, SP=0.0):
        D = max(D, 0.1)
        b = max(b, 0.1)
        term1 = np.arcsinh(D * (data - SP) + b)
        term2 = np.arcsinh(b)
        norm_factor = np.arcsinh(D * (1.0 - SP) + b) - term2
        if abs(norm_factor) < 1e-12:
            norm_factor = 1e-6
        return (term1 - term2) / norm_factor

    @staticmethod
    def solve_log_d(luma_sample, target_median, b_val):
        median_in = np.median(luma_sample)
        if median_in < 1e-9:
            return 2.0
        low_log = 0.0
        high_log = 7.0
        best_log_D = 2.0
        for _ in range(40):
            mid_log = (low_log + high_log) / 2.0
            mid_D = 10.0 ** mid_log
            test_val = VeraLuxCore.hyperbolic_stretch(median_in, mid_D, b_val)
            if abs(test_val - target_median) < 0.0001:
                best_log_D = mid_log
                break
            if test_val < target_median:
                low_log = mid_log
            else:
                high_log = mid_log
            best_log_D = mid_log
        return best_log_D

    @staticmethod
    def apply_mtf(data, m):
        term1 = (m - 1.0) * data
        term2 = (2.0 * m - 1.0) * data - m
        with np.errstate(divide='ignore', invalid='ignore'):
            res = term1 / term2
        return np.nan_to_num(res, nan=0.0, posinf=1.0, neginf=0.0)


# =============================================================================
#  READY-TO-USE SCALING (extrait)
# =============================================================================
RTU_PEDESTAL = 0.001
RTU_SOFT_CEIL_PERCENTILE = 99.0


def adaptive_output_scaling(img_data, working_space="Rec.709 (Recommended)",
                             target_bg=0.20, progress_callback=None):
    luma_r, luma_g, luma_b = SENSOR_PROFILES[working_space]['weights']
    is_rgb = (img_data.ndim == 3 and img_data.shape[0] == 3)

    if is_rgb:
        R, G, B = img_data[0], img_data[1], img_data[2]
        L_raw = luma_r * R + luma_g * G + luma_b * B
    else:
        L_raw = img_data

    median_L = float(np.median(L_raw))
    std_L = float(np.std(L_raw))
    min_L = float(np.min(L_raw))
    global_floor = max(min_L, median_L - 2.7 * std_L)
    PEDESTAL = RTU_PEDESTAL

    abs_max = float(np.max(L_raw))
    valid_physical_max = True

    if abs_max > 0.001:
        idx_max = np.argmax(L_raw)
        y_max, x_max = np.unravel_index(idx_max, L_raw.shape)
        y0, y1 = max(0, y_max - 1), min(L_raw.shape[0], y_max + 2)
        x0, x1 = max(0, x_max - 1), min(L_raw.shape[1], x_max + 2)
        window = L_raw[y0:y1, x0:x1]
        neighbors = window[window < abs_max]
        if neighbors.size > 0:
            max_neighbor = np.max(neighbors)
            if max_neighbor < (abs_max * 0.20):
                valid_physical_max = False

    if is_rgb:
        stride = max(1, R.size // 500000)
        soft_ceil = max(
            np.percentile(R.flatten()[::stride], RTU_SOFT_CEIL_PERCENTILE),
            np.percentile(G.flatten()[::stride], RTU_SOFT_CEIL_PERCENTILE),
            np.percentile(B.flatten()[::stride], RTU_SOFT_CEIL_PERCENTILE)
        )
    else:
        stride = max(1, L_raw.size // 200000)
        soft_ceil = np.percentile(L_raw.flatten()[::stride], RTU_SOFT_CEIL_PERCENTILE)

    if soft_ceil <= global_floor:
        soft_ceil = global_floor + 1e-6
    if abs_max <= soft_ceil:
        abs_max = soft_ceil + 1e-6

    scale_contrast = (0.98 - PEDESTAL) / (soft_ceil - global_floor + 1e-9)

    if valid_physical_max:
        scale_physical_limit = (1.0 - PEDESTAL) / (abs_max - global_floor + 1e-9)
        final_scale = min(scale_contrast, scale_physical_limit)
    else:
        final_scale = scale_contrast

    def expand_channel(c):
        return np.clip((c - global_floor) * final_scale + PEDESTAL, 0.0, 1.0)

    if is_rgb:
        img_data[0] = expand_channel(R)
        img_data[1] = expand_channel(G)
        img_data[2] = expand_channel(B)
        L = luma_r * img_data[0] + luma_g * img_data[1] + luma_b * img_data[2]
    else:
        img_data = expand_channel(L_raw)
        L = img_data

    current_bg = float(np.median(L))
    if 0.0 < current_bg < 1.0 and abs(current_bg - target_bg) > 1e-3:
        m = (current_bg * (target_bg - 1.0)) / (current_bg * (2.0 * target_bg - 1.0) - target_bg)
        if is_rgb:
            for i in range(3):
                img_data[i] = VeraLuxCore.apply_mtf(img_data[i], m)
        else:
            img_data = VeraLuxCore.apply_mtf(img_data, m)
    return img_data


def apply_ready_to_use_soft_clip(img_data, threshold=0.98, rolloff=2.0, progress_callback=None):
    def soft_clip_channel(c, thresh, roll):
        mask = c > thresh
        result = c.copy()
        if np.any(mask):
            t = np.clip((c[mask] - thresh) / (1.0 - thresh + 1e-9), 0.0, 1.0)
            result[mask] = thresh + (1.0 - thresh) * (1.0 - np.power(1.0 - t, roll))
        return np.clip(result, 0.0, 1.0)

    if img_data.ndim == 3:
        for i in range(img_data.shape[0]):
            img_data[i] = soft_clip_channel(img_data[i], threshold, rolloff)
    else:
        img_data = soft_clip_channel(img_data, threshold, rolloff)
    return img_data


def process_veralux_ready_to_use(img_data, log_D, protect_b, convergence_power,
                                  working_space="Rec.709 (Recommended)",
                                  target_bg=0.20, color_grip=1.0, shadow_convergence=0.0,
                                  use_adaptive_anchor=True, progress_callback=None):
    """
    Version simplifiée de process_veralux_v6, restreinte au mode "Ready-to-Use"
    (le mode utilisé dans un pipeline automatisé). Le mode "Scientific" n'est pas
    inclus ici — ajoute-le depuis l'original si besoin un jour.
    """
    img = VeraLuxCore.normalize_input(img_data)
    if img.ndim == 3 and img.shape[0] != 3 and img.shape[2] == 3:
        img = img.transpose(2, 0, 1)

    luma_weights = SENSOR_PROFILES[working_space]['weights']
    is_rgb = (img.ndim == 3 and img.shape[0] == 3)

    if use_adaptive_anchor:
        anchor = VeraLuxCore.calculate_anchor_adaptive(img, weights=luma_weights)
    else:
        anchor = VeraLuxCore.calculate_anchor(img)

    L_anchored, img_anchored = VeraLuxCore.extract_luminance(img, anchor, luma_weights)
    epsilon = 1e-9
    L_safe = L_anchored + epsilon

    if is_rgb:
        r_ratio = img_anchored[0] / L_safe
        g_ratio = img_anchored[1] / L_safe
        b_ratio = img_anchored[2] / L_safe

    L_str = VeraLuxCore.hyperbolic_stretch(L_anchored, 10.0 ** log_D, protect_b)
    L_str = np.clip(L_str, 0.0, 1.0)

    final = np.zeros_like(img)
    if is_rgb:
        k = np.power(L_str, convergence_power)
        r_final = r_ratio * (1.0 - k) + 1.0 * k
        g_final = g_ratio * (1.0 - k) + 1.0 * k
        b_final = b_ratio * (1.0 - k) + 1.0 * k
        final[0] = L_str * r_final
        final[1] = L_str * g_final
        final[2] = L_str * b_final

        needs_hybrid = (color_grip < 1.0) or (shadow_convergence > 0.01)
        if needs_hybrid:
            D_val = 10.0 ** log_D
            scalar = np.zeros_like(final)
            scalar[0] = VeraLuxCore.hyperbolic_stretch(img_anchored[0], D_val, protect_b)
            scalar[1] = VeraLuxCore.hyperbolic_stretch(img_anchored[1], D_val, protect_b)
            scalar[2] = VeraLuxCore.hyperbolic_stretch(img_anchored[2], D_val, protect_b)
            scalar = np.clip(scalar, 0.0, 1.0)
            grip_map = np.full_like(L_str, color_grip)
            if shadow_convergence > 0.01:
                damping = np.power(L_str, shadow_convergence)
                grip_map = grip_map * damping
            final = (final * grip_map) + (scalar * (1.0 - grip_map))
    else:
        final = L_str

    final = final * (1.0 - 0.005) + 0.005
    final = np.clip(final, 0.0, 1.0).astype(np.float32)

    final = adaptive_output_scaling(final, working_space, target_bg, progress_callback)
    final = apply_ready_to_use_soft_clip(final, 0.98, 2.0, progress_callback)

    return final


def compute_diagnostics(final_img, anchor, star_pressure, log_d, working_space, target_bg):
    """Calcule des indicateurs chiffrés exploitables (pas une lecture visuelle)."""
    is_rgb = (final_img.ndim == 3 and final_img.shape[0] == 3)

    if is_rgb:
        luma_r, luma_g, luma_b = SENSOR_PROFILES[working_space]['weights']
        L = luma_r * final_img[0] + luma_g * final_img[1] + luma_b * final_img[2]
    else:
        L = final_img

    # Percentiles de LUMINANCE (plus révélateur qu'un seuil AND sur 3 canaux séparés,
    # qui ne se déclenche presque jamais à cause du bruit chromatique résiduel)
    percentiles = np.percentile(L, [0.1, 1, 5, 50, 95, 99, 99.9])

    return {
        "log_d_resolu": round(float(log_d), 4),
        "anchor": round(float(anchor), 6),
        "star_pressure": round(float(star_pressure), 4),
        "target_bg_demande": float(target_bg),
        "median_luminance_finale": round(float(np.median(L)), 6),
        "std_luminance_finale": round(float(np.std(L)), 6),
        "luminance_percentiles": {
            "p0.1": round(float(percentiles[0]), 6),
            "p1": round(float(percentiles[1]), 6),
            "p5": round(float(percentiles[2]), 6),
            "p50_mediane": round(float(percentiles[3]), 6),
            "p95": round(float(percentiles[4]), 6),
            "p99": round(float(percentiles[5]), 6),
            "p99.9": round(float(percentiles[6]), 6),
        },
        "sensor_profile": working_space,
    }


def solve_and_stretch(img_data, working_space="Rec.709 (Recommended)",
                       target_bg=0.20, protect_b=6.0, convergence_power=3.5,
                       use_adaptive_anchor=True, log_d_override=None,
                       color_grip=1.0, shadow_convergence=0.0):
    """
    Fonction "tout-en-un" : résout le Log D optimal (sauf si log_d_override est fourni)
    puis applique le stretch complet. Retourne aussi un dict de diagnostics chiffrés.
    """
    luma_weights = SENSOR_PROFILES[working_space]['weights']
    star_pressure = 0.0
    anchor = 0.0

    if log_d_override is not None:
        log_d = float(log_d_override)
    else:
        img_norm = VeraLuxCore.normalize_input(img_data)
        if img_norm.ndim == 3 and img_norm.shape[0] != 3 and img_norm.shape[2] == 3:
            img_norm = img_norm.transpose(2, 0, 1)

        if img_norm.ndim == 3:
            h, w = img_norm.shape[1], img_norm.shape[2]
            step = max(1, (h * w) // 100000)
            sub_data = np.vstack([img_norm[c].flatten()[::step] for c in range(3)])
        else:
            step = max(1, img_norm.size // 100000)
            sub_data = img_norm.flatten()[::step]

        if use_adaptive_anchor:
            anchor = VeraLuxCore.calculate_anchor_adaptive(sub_data, weights=luma_weights)
        else:
            anchor = VeraLuxCore.calculate_anchor(sub_data)

        L_anchored, _ = VeraLuxCore.extract_luminance(sub_data, anchor, luma_weights)
        valid = L_anchored[L_anchored > 1e-7]
        star_pressure = VeraLuxCore.estimate_star_pressure(L_anchored)

        if len(valid) == 0:
            log_d = 2.0
        else:
            target_temp = target_bg
            log_d = 2.0
            for _ in range(15):
                log_d = VeraLuxCore.solve_log_d(valid, target_temp, protect_b)
                if star_pressure > 0.6:
                    target_temp *= (1.0 - 0.15 * star_pressure)
                D = 10.0 ** log_d
                valid_str = VeraLuxCore.hyperbolic_stretch(valid, D, protect_b)
                med = float(np.median(valid_str))
                std = float(np.std(valid_str))
                min_v = float(np.min(valid_str))
                global_floor = max(min_v, med - 2.7 * std)
                if global_floor <= 0.001:
                    break
                target_temp -= 0.015
                if target_temp < 0.05:
                    break

    result = process_veralux_ready_to_use(
        img_data, log_d, protect_b, convergence_power,
        working_space=working_space, target_bg=target_bg,
        color_grip=color_grip, shadow_convergence=shadow_convergence,
        use_adaptive_anchor=use_adaptive_anchor
    )

    diagnostics = compute_diagnostics(result, anchor, star_pressure, log_d, working_space, target_bg)

    return result, log_d, diagnostics
