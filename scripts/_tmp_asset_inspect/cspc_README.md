# COIN-D6 LiDAR ROS2 Driver

ROS2 driver package for CSPC M1CT_TOF LiDAR sensor.

## Hardware Setup

![LiDAR Hardware Connection](images/lidar.jpg)
_LiDAR connected via USB_

## Visualization

![RViz Visualization](images/Screenshot.png)
_Real-time LaserScan data visualization in RViz2_

## Features

- **High Update Rate**: 10 Hz scan rate (10 rotations per second)
- **Intensity Data**: Provides reflectivity information for better object recognition
- **Long Range**: Up to 16 meters detection range
- **Wide FOV**: 360-degree field of view
- **ROS2 Support**: Compatible with ROS2 Humble and Jazzy

## Specifications

| Parameter          | Value                           |
| ------------------ | ------------------------------- |
| Model              | M1CT_TOF                        |
| Scan Rate          | 10 Hz                           |
| Range              | 0.01m - 16m                     |
| Angular Resolution | ~1 degree (353 points per scan) |
| Baudrate           | 230400                          |
| Interface          | USB Serial (CH340 chip)         |

## Prerequisites

- ROS2 (Humble or Jazzy)
- Ubuntu 22.04 (Humble) or Ubuntu 24.04 (Jazzy)
- PCL (Point Cloud Library)

## Installation

### 1. Clone the Repository

```bash
cd ~/ros2_ws/src
git clone <repository_url> cspc_lidar_sdk_ros2
```

### 2. Install Dependencies

```bash
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
```

### 3. Setup USB Device Rule

This creates a fixed device name `/dev/ttyLIDAR` so you don't need to worry about `/dev/ttyUSB0`, `/dev/ttyUSB1`, etc., changing.

```bash
cd ~/ros2_ws/src/cspc_lidar_sdk_ros2
sudo ./setup_lidar_udev.sh
```

**Note**: After running this script, you no longer need to run `sudo chmod 777 /dev/ttyUSB*` every time you reconnect the LiDAR.

### 4. Build the Package

```bash
cd ~/ros2_ws
colcon build --packages-select cspc_lidar
source install/setup.bash
```

## Usage

### Launch LiDAR Node

```bash
ros2 launch cspc_lidar lidar_launch.py
```

### Launch with RViz Visualization

```bash
ros2 launch cspc_lidar lidar_rviz.py
```

### Check Data Publishing Rate

```bash
ros2 topic hz /scan
```

Expected output: ~10 Hz

### View Scan Data

```bash
ros2 topic echo /scan --once
```

## Published Topics

| Topic          | Type                      | Description                                           |
| -------------- | ------------------------- | ----------------------------------------------------- |
| `/scan`        | `sensor_msgs/LaserScan`   | Laser scan data with intensity                        |
| `/point_cloud` | `sensor_msgs/PointCloud2` | 3D point cloud representation                         |
| `/lsd_error`   | `std_msgs/String`         | Error messages (trapped, frequency abnormal, blocked) |

## Parameters

Parameters can be configured in `params/cspc_lidar.yaml`:

| Parameter   | Default         | Description                      |
| ----------- | --------------- | -------------------------------- |
| `port`      | `/dev/ttyLIDAR` | Serial port device               |
| `baudrate`  | `230400`        | Communication baudrate           |
| `frame_id`  | `laser_link`    | TF frame ID                      |
| `angle_min` | `-180.0`        | Minimum scan angle (degrees)     |
| `angle_max` | `180.0`         | Maximum scan angle (degrees)     |
| `min_range` | `0.01`          | Minimum detection range (meters) |
| `max_range` | `16.0`          | Maximum detection range (meters) |
| `frequency` | `10.0`          | Target scan frequency (Hz)       |
| `version`   | `4`             | LiDAR version (4 = M1CT_TOF)     |

## Troubleshooting

### LiDAR not detected

1. Check USB connection:

   ```bash
   ls -l /dev/ttyLIDAR
   ```

2. If `/dev/ttyLIDAR` doesn't exist, re-run the setup script:

   ```bash
   sudo ./setup_lidar_udev.sh
   ```

3. Unplug and replug the USB cable

### "trapped" or "blocked" error

This indicates the LiDAR's motor is physically obstructed:

- Check if the rotating part can spin freely
- Remove any obstacles or debris
- Ensure adequate power supply through USB

### Low scan rate

Check the actual rate:

```bash
ros2 topic hz /scan
```

If significantly lower than 10 Hz:

- Check USB cable quality
- Try a different USB port
- Restart the LiDAR node

### Permission denied error

If you see permission errors and haven't run the setup script:

```bash
sudo chmod 666 /dev/ttyUSB0  # Temporary fix
# Or better:
sudo ./setup_lidar_udev.sh   # Permanent fix
```

## RViz Configuration

### Intensity Visualization (Rainbow Colors)

The LiDAR provides intensity data, which is displayed as rainbow colors in RViz:

- **Red/Yellow**: High reflectivity (bright surfaces, metal, white walls)
- **Green**: Medium reflectivity
- **Blue/Purple**: Low reflectivity (dark surfaces, black objects)

### Change to Single Color

In RViz:

1. Select the **LaserScan** display
2. Change **Color Transformer** to `FlatColor`
3. Set your preferred color

## License

Please refer to the manufacturer's license agreement.

## Support

For issues related to:

- **Hardware**: Contact CSPC manufacturer
- **ROS2 Driver**: Open an issue in this repository

## Version History

- **v1.0.0** (2026-02-09)
  - Initial ROS2 Jazzy support
  - Fixed compilation warnings
  - Added udev rule setup script
  - Improved documentation
