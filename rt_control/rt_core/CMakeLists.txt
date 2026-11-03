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
  src/robot_state_machine.cpp
)
target_include_directories(rt_core PUBLIC include)
target_link_libraries(rt_core PUBLIC Threads::Threads)
target_compile_options(rt_core PRIVATE -Wall -Wextra)

# ---------------------------------------------------------------------------
# 선택: MuJoCo 백엔드. 켜려면  cmake -DRT_CORE_WITH_MUJOCO=ON -DMUJOCO_DIR=<경로>
#   <경로>/include/mujoco/mujoco.h 와 <경로>/lib/libmujoco.so 가 있어야 한다 (scripts/get_mujoco.sh 가 third_party/mujoco 에 받아 준다)
#   기본 OFF: MuJoCo 가 없는 PC·CI 1단계에서도 rt_core 가 그대로 빌드되게.
# ---------------------------------------------------------------------------
option(RT_CORE_WITH_MUJOCO "MuJoCo 물리 시뮬레이터 백엔드 포함" OFF)
if(RT_CORE_WITH_MUJOCO)
  set(MUJOCO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/mujoco" CACHE PATH "MuJoCo 설치 경로 (include/, lib/)")
  find_path(MUJOCO_INCLUDE_DIR mujoco/mujoco.h HINTS ${MUJOCO_DIR}/include)
  find_library(MUJOCO_LIBRARY NAMES mujoco HINTS ${MUJOCO_DIR}/lib)
  if(NOT MUJOCO_INCLUDE_DIR OR NOT MUJOCO_LIBRARY)
    message(FATAL_ERROR "MuJoCo 를 찾지 못함 (MUJOCO_DIR=${MUJOCO_DIR}). scripts/get_mujoco.sh 를 먼저 실행하거나 -DMUJOCO_DIR=<경로>")
  endif()
  get_filename_component(MUJOCO_LIB_DIR ${MUJOCO_LIBRARY} DIRECTORY)
  target_sources(rt_core PRIVATE src/mujoco_backend.cpp)
  target_include_directories(rt_core PUBLIC ${MUJOCO_INCLUDE_DIR})
  target_link_libraries(rt_core PUBLIC ${MUJOCO_LIBRARY})
  target_link_options(rt_core PUBLIC "-Wl,-rpath,${MUJOCO_LIB_DIR}")   # 실행 파일이 libmujoco.so 를 찾게 (LD_LIBRARY_PATH 없이)
  target_compile_definitions(rt_core PUBLIC RT_CORE_WITH_MUJOCO=1)
  message(STATUS "MuJoCo 백엔드 포함: ${MUJOCO_LIBRARY}")
endif()

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

  add_executable(test_state_machine test/test_state_machine.cpp)
  target_link_libraries(test_state_machine PRIVATE rt_core)
  add_test(NAME state_machine COMMAND test_state_machine)

  # RT 권한이 없는 CI 러너에서도 도는 연기 테스트: 1 kHz 2초, 드롭 0이어야 통과
  add_test(NAME jitter_smoke COMMAND jitter_bench --no-rt --seconds 2 --period-us 1000 --label ci_smoke)

  if(RT_CORE_WITH_MUJOCO)
    # 모델 경로는 환경변수 RT_MUJOCO_MODEL 로 (CI 는 menagerie 의 SO-ARM100 scene.xml)
    add_executable(test_mujoco_backend test/test_mujoco_backend.cpp)
    target_link_libraries(test_mujoco_backend PRIVATE rt_core)
    add_test(NAME mujoco_backend COMMAND test_mujoco_backend)
  endif()
endif()
