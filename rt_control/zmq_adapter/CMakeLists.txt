cmake_minimum_required(VERSION 3.16)
project(rt_control_zmq LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# ROS 2 노드(ros2_adapter)와 같은 핵심 라이브러리를 그대로 쓴다 — 껍질만 ZeroMQ
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../rt_core ${CMAKE_CURRENT_BINARY_DIR}/rt_core)

# libzmq (Ubuntu: sudo apt-get install libzmq3-dev). C API 만 쓴다 — cppzmq 같은 감싸개 없이
#   찾는 순서: -DZMQ_INCLUDE_DIR / -DZMQ_LIBRARY 로 준 값 → pkg-config libzmq
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
  pkg_check_modules(PC_ZMQ QUIET libzmq)
endif()
find_path(ZMQ_INCLUDE_DIR zmq.h HINTS ${PC_ZMQ_INCLUDE_DIRS})
find_library(ZMQ_LIBRARY NAMES zmq libzmq.so.5 HINTS ${PC_ZMQ_LIBRARY_DIRS})
if(NOT ZMQ_INCLUDE_DIR OR NOT ZMQ_LIBRARY)
  message(FATAL_ERROR "libzmq 를 찾지 못함 — sudo apt-get install libzmq3-dev")
endif()
message(STATUS "libzmq: ${ZMQ_LIBRARY}")

add_executable(rt_zmq_node src/rt_zmq_node.cpp)
target_include_directories(rt_zmq_node PRIVATE ${ZMQ_INCLUDE_DIR})
target_link_libraries(rt_zmq_node PRIVATE rt_core ${ZMQ_LIBRARY})
target_compile_options(rt_zmq_node PRIVATE -Wall -Wextra)

# 같은 PC 에서 공유 메모리로 최신 상태를 읽는 도구 (소켓 없이) — C++ 쪽 읽기 예시
add_executable(rt_state_peek src/rt_state_peek.cpp)
target_link_libraries(rt_state_peek PRIVATE rt_core)
target_compile_options(rt_state_peek PRIVATE -Wall -Wextra)

install(TARGETS rt_zmq_node rt_state_peek DESTINATION bin)
