cmake_minimum_required(VERSION 3.16)
project(rt_control_ros2 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rmw REQUIRED)

# ROS 2 와 무관한 핵심 라이브러리를 그대로 가져다 쓴다 (한 벌의 코드, 두 곳에서 빌드)
#   MuJoCo 백엔드까지 넣으려면:  colcon build --cmake-args -DRT_CORE_WITH_MUJOCO=ON -DMUJOCO_DIR=$PWD/third_party/mujoco
#   (옵션은 rt_core 의 CMakeLists 가 받는다. 컴파일 정의 RT_CORE_WITH_MUJOCO 가 이 노드까지 전해진다)
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../rt_core ${CMAKE_CURRENT_BINARY_DIR}/rt_core)
set(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)   # install 된 실행 파일도 libmujoco.so 위치를 기억하게 (LD_LIBRARY_PATH 불필요)

add_executable(rt_control_node src/rt_control_node.cpp)
target_link_libraries(rt_control_node rt_core)
ament_target_dependencies(rt_control_node rclcpp sensor_msgs std_msgs rmw)
target_compile_options(rt_control_node PRIVATE -Wall -Wextra)

install(TARGETS rt_control_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config DESTINATION share/${PROJECT_NAME})

ament_package()
