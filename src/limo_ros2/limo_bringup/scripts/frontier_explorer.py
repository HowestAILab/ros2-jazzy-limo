#!/usr/bin/env python3
"""
Simple Frontier Explorer for LIMO
Finds unexplored areas in the SLAM map and navigates to them.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseStamped, Point
from visualization_msgs.msg import Marker, MarkerArray
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus
import numpy as np
from scipy import ndimage
import math
import tf2_ros
from tf2_ros import TransformException


class FrontierExplorer(Node):
    def __init__(self):
        super().__init__('frontier_explorer')
        
        # Parameters
        self.declare_parameter('map_topic', '/map')
        self.declare_parameter('min_frontier_size', 5)  # Minimum cells to be a valid frontier
        self.declare_parameter('robot_base_frame', 'base_link')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('goal_tolerance', 0.5)  # meters
        self.declare_parameter('exploration_timeout', 60.0)  # seconds per goal
        self.declare_parameter('frontier_blacklist_radius', 1.0)  # Don't revisit failed frontiers
        
        self.map_topic = self.get_parameter('map_topic').value
        self.min_frontier_size = self.get_parameter('min_frontier_size').value
        self.robot_base_frame = self.get_parameter('robot_base_frame').value
        self.map_frame = self.get_parameter('map_frame').value
        self.goal_tolerance = self.get_parameter('goal_tolerance').value
        self.exploration_timeout = self.get_parameter('exploration_timeout').value
        self.blacklist_radius = self.get_parameter('frontier_blacklist_radius').value
        
        # State
        self.current_map = None
        self.map_info = None
        self.robot_pose = None
        self.is_navigating = False
        self.current_goal = None
        self.blacklisted_points = []  # Failed frontier locations
        self.exploration_complete = False
        
        # TF
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Subscribers
        self.map_sub = self.create_subscription(
            OccupancyGrid,
            self.map_topic,
            self.map_callback,
            10
        )
        
        # Publishers for visualization
        self.frontier_pub = self.create_publisher(MarkerArray, 'frontiers', 10)
        self.goal_pub = self.create_publisher(Marker, 'exploration_goal', 10)
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Timer for exploration loop
        self.explore_timer = self.create_timer(2.0, self.exploration_loop)
        
        self.get_logger().info('Frontier Explorer initialized!')
        self.get_logger().info(f'Subscribing to map on: {self.map_topic}')
        self.get_logger().info('Waiting for map and Nav2...')

    def map_callback(self, msg):
        """Store the latest map."""
        self.current_map = np.array(msg.data).reshape(msg.info.height, msg.info.width)
        self.map_info = msg.info
        
    def get_robot_pose(self):
        """Get current robot position in map frame."""
        try:
            transform = self.tf_buffer.lookup_transform(
                self.map_frame,
                self.robot_base_frame,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=1.0)
            )
            self.robot_pose = (
                transform.transform.translation.x,
                transform.transform.translation.y
            )
            return self.robot_pose
        except TransformException as e:
            self.get_logger().warn(f'Could not get robot pose: {e}')
            return None

    def find_frontiers(self):
        """
        Find frontier cells in the map.
        Frontiers are free cells (0) adjacent to unknown cells (-1).
        """
        if self.current_map is None:
            return []
        
        map_data = self.current_map.copy()
        
        # Create masks
        free_mask = map_data == 0  # Free space
        unknown_mask = map_data == -1  # Unknown space
        
        # Dilate unknown to find cells adjacent to unknown
        kernel = np.ones((3, 3), dtype=np.uint8)
        unknown_dilated = ndimage.binary_dilation(unknown_mask, kernel)
        
        # Frontiers are free cells that are adjacent to unknown
        frontier_mask = free_mask & unknown_dilated
        
        # Label connected frontier regions
        labeled, num_features = ndimage.label(frontier_mask)
        
        frontiers = []
        for i in range(1, num_features + 1):
            # Get cells belonging to this frontier
            frontier_cells = np.argwhere(labeled == i)
            
            if len(frontier_cells) >= self.min_frontier_size:
                # Calculate centroid in map coordinates
                centroid_y, centroid_x = frontier_cells.mean(axis=0)
                
                # Convert to world coordinates
                world_x = self.map_info.origin.position.x + centroid_x * self.map_info.resolution
                world_y = self.map_info.origin.position.y + centroid_y * self.map_info.resolution
                
                # Check if this frontier is blacklisted
                if not self.is_blacklisted(world_x, world_y):
                    frontiers.append({
                        'x': world_x,
                        'y': world_y,
                        'size': len(frontier_cells),
                        'cells': frontier_cells
                    })
        
        return frontiers

    def is_blacklisted(self, x, y):
        """Check if a point is too close to a blacklisted location."""
        for bx, by in self.blacklisted_points:
            dist = math.sqrt((x - bx)**2 + (y - by)**2)
            if dist < self.blacklist_radius:
                return True
        return False

    def select_best_frontier(self, frontiers):
        """
        Select the best frontier to explore.
        Strategy: Balance between distance and frontier size.
        """
        if not frontiers or self.robot_pose is None:
            return None
        
        robot_x, robot_y = self.robot_pose
        
        best_frontier = None
        best_score = float('-inf')
        
        for frontier in frontiers:
            distance = math.sqrt(
                (frontier['x'] - robot_x)**2 + 
                (frontier['y'] - robot_y)**2
            )
            
            # Avoid very close frontiers (might be noise)
            if distance < 0.3:
                continue
            
            # Score: prefer larger frontiers, penalize distance
            # Tune these weights based on your environment
            size_weight = 1.0
            distance_weight = 0.5
            
            score = size_weight * frontier['size'] - distance_weight * distance
            
            if score > best_score:
                best_score = score
                best_frontier = frontier
        
        return best_frontier

    def send_nav_goal(self, x, y):
        """Send a navigation goal to Nav2."""
        if not self.nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('Nav2 action server not available!')
            return False
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = self.map_frame
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.orientation.w = 1.0  # Face forward
        
        self.get_logger().info(f'Sending goal to frontier at ({x:.2f}, {y:.2f})')
        
        self.current_goal = (x, y)
        self.is_navigating = True
        
        send_goal_future = self.nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self.nav_feedback_callback
        )
        send_goal_future.add_done_callback(self.goal_response_callback)
        
        return True

    def goal_response_callback(self, future):
        """Handle goal acceptance/rejection."""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Goal rejected by Nav2')
            self.is_navigating = False
            # Blacklist this point
            if self.current_goal:
                self.blacklisted_points.append(self.current_goal)
            return
        
        self.get_logger().info('Goal accepted!')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.goal_result_callback)

    def goal_result_callback(self, future):
        """Handle navigation result."""
        result = future.result()
        status = result.status
        
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info('Reached frontier successfully!')
        elif status == GoalStatus.STATUS_ABORTED:
            self.get_logger().warn('Navigation aborted - blacklisting frontier')
            if self.current_goal:
                self.blacklisted_points.append(self.current_goal)
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().info('Navigation canceled')
        else:
            self.get_logger().warn(f'Navigation ended with status: {status}')
            if self.current_goal:
                self.blacklisted_points.append(self.current_goal)
        
        self.is_navigating = False
        self.current_goal = None

    def nav_feedback_callback(self, feedback_msg):
        """Handle navigation feedback (optional logging)."""
        pass  # Could log progress here

    def publish_visualization(self, frontiers, selected_frontier):
        """Publish visualization markers for RViz."""
        # Publish all frontiers
        marker_array = MarkerArray()
        
        for i, frontier in enumerate(frontiers):
            marker = Marker()
            marker.header.frame_id = self.map_frame
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = 'frontiers'
            marker.id = i
            marker.type = Marker.SPHERE
            marker.action = Marker.ADD
            marker.pose.position.x = frontier['x']
            marker.pose.position.y = frontier['y']
            marker.pose.position.z = 0.1
            marker.scale.x = 0.3
            marker.scale.y = 0.3
            marker.scale.z = 0.3
            marker.color.r = 0.0
            marker.color.g = 0.0
            marker.color.b = 1.0
            marker.color.a = 0.7
            marker_array.markers.append(marker)
        
        # Clear old markers
        delete_marker = Marker()
        delete_marker.action = Marker.DELETEALL
        
        self.frontier_pub.publish(marker_array)
        
        # Publish selected goal
        if selected_frontier:
            goal_marker = Marker()
            goal_marker.header.frame_id = self.map_frame
            goal_marker.header.stamp = self.get_clock().now().to_msg()
            goal_marker.ns = 'goal'
            goal_marker.id = 0
            goal_marker.type = Marker.ARROW
            goal_marker.action = Marker.ADD
            goal_marker.pose.position.x = selected_frontier['x']
            goal_marker.pose.position.y = selected_frontier['y']
            goal_marker.pose.position.z = 0.5
            goal_marker.scale.x = 0.5
            goal_marker.scale.y = 0.1
            goal_marker.scale.z = 0.1
            goal_marker.color.r = 0.0
            goal_marker.color.g = 1.0
            goal_marker.color.b = 0.0
            goal_marker.color.a = 1.0
            self.goal_pub.publish(goal_marker)

    def exploration_loop(self):
        """Main exploration loop - called periodically."""
        if self.exploration_complete:
            return
            
        if self.current_map is None:
            self.get_logger().info('Waiting for map...', throttle_duration_sec=5.0)
            return
        
        if self.is_navigating:
            return  # Already navigating to a frontier
        
        # Get robot position
        if not self.get_robot_pose():
            self.get_logger().warn('Cannot get robot pose', throttle_duration_sec=5.0)
            return
        
        # Find frontiers
        frontiers = self.find_frontiers()
        
        if not frontiers:
            self.get_logger().info('No frontiers found - exploration complete!')
            self.exploration_complete = True
            return
        
        self.get_logger().info(f'Found {len(frontiers)} frontiers')
        
        # Select best frontier
        best = self.select_best_frontier(frontiers)
        
        # Publish visualization
        self.publish_visualization(frontiers, best)
        
        if best:
            self.send_nav_goal(best['x'], best['y'])
        else:
            self.get_logger().warn('No suitable frontier found')


def main(args=None):
    rclpy.init(args=args)
    node = FrontierExplorer()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()