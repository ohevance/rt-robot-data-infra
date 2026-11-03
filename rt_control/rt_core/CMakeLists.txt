cmake_minimum_required(VERSION 3.16)
project(rt_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(Threads REQUIRED)

# ROS 2와 무관한 순수 C++ 라이브러리. ROS 2 노드는 이것을 링크하는 얇은 어댑터.
add_library(rt_core STATIC
  src/rt_loop.cpp
  src/control_step.cpp
  src/sim_lag_backend.cpp
)
target_include_directories(rt_core PUBLIC include)
target_link_libraries(rt_core PUBLIC Threads::Threads)
target_compile_options(rt_core PRIVATE -Wall -Wextra)

add_executable(jitter_bench src/jitter_bench.cpp)
target_link_libraries(jitter_bench PRIVATE rt_core)
target_compile_options(jitter_bench PRIVATE -Wall -Wextra)

# 테스트는 최상위 빌드일 때만 등록한다 (ROS 2 패키지가 add_subdirectory 로 가져다 쓸 때는 건너뜀)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  enable_testing()

  add_executable(test_spsc_ring test/test_spsc_ring.cpp)
  target_include_directories(test_spsc_ring PRIVATE include)
  target_link_libraries(test_spsc_ring PRIVATE Threads::Threads)
  add_test(NAME spsc_ring COMMAND test_spsc_ring)

  add_executable(test_control_step test/test_control_step.cpp)
  target_link_libraries(test_control_step PRIVATE rt_core)
  add_test(NAME control_step COMMAND test_control_step)

  # RT 권한이 없는 CI 러너에서도 도는 연기 테스트: 1 kHz 2초, 드롭 0이어야 통과
  add_test(NAME jitter_smoke COMMAND jitter_bench --no-rt --seconds 2 --period-us 1000 --label ci_smoke)
endif()
