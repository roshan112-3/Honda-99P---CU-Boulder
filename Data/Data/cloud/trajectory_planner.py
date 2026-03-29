from sensor_fusion import fuse_obstacle_track


def plan_avoidance_trajectory(raw_distance_m, raw_lateral_m):
    fused = fuse_obstacle_track(raw_distance_m, raw_lateral_m)
    return fused["distance_m"] > 4.0 and abs(fused["lateral_m"]) <= 0.52


def collision_margin_nominal(raw_distance_m, raw_lateral_m):
    return plan_avoidance_trajectory(raw_distance_m, raw_lateral_m)
