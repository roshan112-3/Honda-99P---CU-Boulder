from sensor_fusion import obstacle_detection_accuracy, sensor_fusion_integration
from trajectory_planner import collision_margin_nominal, plan_avoidance_trajectory


def test_obstacle_detection_accuracy():
    return obstacle_detection_accuracy(8.0, 0.48)


def test_collision_margin_nominal():
    return collision_margin_nominal(8.0, 0.48)


def test_trajectory_planner_clearance():
    return plan_avoidance_trajectory(8.0, 0.48)


def test_sensor_fusion_integration():
    return sensor_fusion_integration(8.0, 0.48)
