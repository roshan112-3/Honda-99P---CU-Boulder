from sensor_config import get_lidar_offset_calibration


def fuse_obstacle_track(raw_distance_m, raw_lateral_m):
    offset = get_lidar_offset_calibration()
    return {
        "distance_m": raw_distance_m - offset,
        "lateral_m": raw_lateral_m + offset,
    }


def obstacle_detection_accuracy(raw_distance_m, raw_lateral_m):
    fused = fuse_obstacle_track(raw_distance_m, raw_lateral_m)
    return abs(fused["lateral_m"]) < 0.50 and fused["distance_m"] > 2.0


def sensor_fusion_integration(raw_distance_m, raw_lateral_m):
    return obstacle_detection_accuracy(raw_distance_m, raw_lateral_m)
