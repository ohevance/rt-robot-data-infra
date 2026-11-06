// ===========================================================================
// 파일 역할 : MujocoBackend 테스트 — 진짜 MuJoCo + 진짜 로봇 모델로, 화면 없이.
//             기본은 SO-ARM100(menagerie, 6관절). 환경변수로 다른 모델(ALLEX 48관절 등)도 같은 코드로 돌린다.
//
// 확인하는 것
//   1) 모델이 로드되고 관절 dof 개가 액추에이터에 연결된다
//   2) 관절 0 에 +0.3 rad 목표를 주고 1 kHz 로 2000 주기(2초) 돌리면 위치가 목표 쪽으로 간다 (물리 모델이 움직인다)
//   3) 한 주기(write_command = mj_step + read_state)에 걸리는 시간: p99 가 주기(1 ms)의 90% 아래 → "1 kHz 안에 들어온다"
//      max 는 참고로만 출력 (CI 러너는 RT 가 아니라 가끔 튄다)
//   결과는 JSON 으로 저장 (CI 아티팩트)
//
// 실행 (환경변수):
//   RT_MUJOCO_MODEL   모델 xml 경로 (필수)            예: third_party/mujoco_menagerie/trs_so_arm100/scene.xml
//   RT_MUJOCO_DOF     관절 수 (기본 6)                 예: 48
//   RT_MUJOCO_JOINTS  쉼표로 이은 관절 이름 (기본 비움 = 모델 순서대로 앞 dof 개)
//                     예: $(python3 scripts/profile_joints.py robots/allex.yaml)
//   RT_MUJOCO_OUT     결과 JSON 파일 이름 (기본 mujoco_backend_ci.json)
//
// 읽는 순서: TestConfig(환경변수 읽기) → split_csv → main (모델 로드 → 2000 주기 → 통계 → JSON)
// ===========================================================================
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "rt_core/mujoco_backend.hpp"
#include "rt_core/rt_clock.hpp"

static int g_fail_count = 0;

static void check(bool condition, const char* message) {
  if (!condition) {
    std::fprintf(stderr, "FAIL: %s\n", message);
    g_fail_count = g_fail_count + 1;
  }
}

static double percentile_us(std::vector<std::int64_t>& sorted_ns, double p) {
  std::size_t n = sorted_ns.size();
  std::size_t index = static_cast<std::size_t>(std::ceil(p / 100.0 * static_cast<double>(n)));
  if (index < 1) {
    index = 1;
  }
  if (index > n) {
    index = n;
  }
  return static_cast<double>(sorted_ns[index - 1]) / 1000.0;
}

// "a,b,c" → {"a","b","c"}. 빈 문자열이면 빈 목록 (= 모델 순서대로).
static std::vector<std::string> split_csv(const char* text) {
  std::vector<std::string> out;
  if (text == nullptr || text[0] == '\0') {
    return out;
  }
  std::string s(text);
  std::size_t start = 0;
  while (start <= s.size()) {
    std::size_t comma = s.find(',', start);
    if (comma == std::string::npos) {
      comma = s.size();
    }
    std::string item = s.substr(start, comma - start);
    if (!item.empty()) {
      out.push_back(item);
    }
    start = comma + 1;
  }
  return out;
}

// 환경변수에서 읽는 설정. 기본값은 SO-ARM100 6관절 (기존 CI 와 같은 동작).
struct TestConfig {
  const char* model_path = nullptr;
  std::uint32_t dof = 6;
  std::vector<std::string> joints;
  std::string out_json = "mujoco_backend_ci.json";
};

static bool read_config(int argc, char** argv, TestConfig& cfg) {
  cfg.model_path = std::getenv("RT_MUJOCO_MODEL");
  if (argc > 1) {
    cfg.model_path = argv[1];
  }
  if (cfg.model_path == nullptr) {
    std::fprintf(stderr, "RT_MUJOCO_MODEL 환경변수(모델 xml 경로)를 설정하세요. 예:\n"
                         "  RT_MUJOCO_MODEL=third_party/mujoco_menagerie/trs_so_arm100/scene.xml %s\n", argv[0]);
    return false;
  }
  const char* dof_text = std::getenv("RT_MUJOCO_DOF");
  if (dof_text != nullptr && dof_text[0] != '\0') {
    cfg.dof = static_cast<std::uint32_t>(std::atoi(dof_text));
  }
  if (cfg.dof == 0 || cfg.dof > rt_core::kMaxJoints) {
    std::fprintf(stderr, "RT_MUJOCO_DOF=%u 는 1..%u 범위가 아님\n", cfg.dof, rt_core::kMaxJoints);
    return false;
  }
  cfg.joints = split_csv(std::getenv("RT_MUJOCO_JOINTS"));
  if (!cfg.joints.empty() && cfg.joints.size() != cfg.dof) {
    std::fprintf(stderr, "RT_MUJOCO_JOINTS 이름 %zu개 != RT_MUJOCO_DOF %u\n", cfg.joints.size(), cfg.dof);
    return false;
  }
  const char* out_text = std::getenv("RT_MUJOCO_OUT");
  if (out_text != nullptr && out_text[0] != '\0') {
    cfg.out_json = out_text;
  }
  return true;
}

int main(int argc, char** argv) {
  TestConfig cfg;
  if (!read_config(argc, argv, cfg)) {
    return 2;
  }
  const std::uint32_t dof = cfg.dof;
  const std::int64_t period_ns = 1000000;  // 1 ms
  const int cycles = 2000;                 // 2 초

  rt_core::MujocoBackend backend;
  backend.set_model(cfg.model_path);
  // 관절 이름을 주지 않으면 모델 순서대로 앞 dof 개 (SO-ARM100 은 그래도 맞는다). ALLEX 처럼 수동 관절이 섞인 모델은 이름을 준다.
  if (!cfg.joints.empty()) {
    backend.set_joint_names(cfg.joints);
  }
  bool ok = backend.init(dof, period_ns);
  check(ok, "init: 모델 로드 + 관절/액추에이터 연결");
  if (!ok) {
    return 1;
  }
  check(backend.substeps() >= 1, "substeps >= 1");
  check(backend.sim_timestep_s() <= 0.001 + 1e-12, "시뮬레이션 걸음 <= 제어 주기");

  // 버퍼는 컴파일 때 최대 관절 수로 잡고(노드와 같은 규칙), dof 개만 쓴다
  double target[rt_core::kMaxJoints] = {0.0};
  double position[rt_core::kMaxJoints] = {0.0};
  double velocity[rt_core::kMaxJoints] = {0.0};
  backend.read_state(position, velocity, dof);
  for (std::uint32_t i = 0; i < dof; ++i) {
    target[i] = position[i];  // 나머지 관절은 현재 위치를 유지 (중력에 떨어지지 않게)
  }
  double start_pos0 = position[0];
  target[0] = start_pos0 + 0.3;  // 관절 0 을 0.3 rad 움직이라고 명령

  std::vector<std::int64_t> cycle_ns;
  cycle_ns.reserve(cycles);
  for (int c = 0; c < cycles; ++c) {
    std::int64_t t0 = rt_core::now_ns();
    backend.write_command(target, dof);
    backend.read_state(position, velocity, dof);
    std::int64_t t1 = rt_core::now_ns();
    cycle_ns.push_back(t1 - t0);
  }

  double moved = position[0] - start_pos0;
  std::printf("관절 0 (%s): 시작 %.3f → 2초 뒤 %.3f rad (목표 +0.300, 움직임 %.3f)\n", backend.joint_name(0).c_str(),
              start_pos0, position[0], moved);
  check(moved > 0.15, "2초 뒤 관절 0 이 목표의 절반 이상 움직였다 (물리 모델이 명령에 반응)");
  check(std::fabs(moved) < 0.6, "과도하게 튀지 않았다");

  std::sort(cycle_ns.begin(), cycle_ns.end());
  double p50 = percentile_us(cycle_ns, 50.0);
  double p99 = percentile_us(cycle_ns, 99.0);
  double mx = static_cast<double>(cycle_ns.back()) / 1000.0;
  std::printf("한 주기 비용 (mj_step x %d + read, %u 관절): p50 %.1f us, p99 %.1f us, max %.1f us  (주기 1000 us)\n",
              backend.substeps(), dof, p50, p99, mx);
  check(p99 < 900.0, "p99 < 900 us: 1 kHz 주기 안에 물리 한 걸음이 들어온다");

  std::FILE* f = std::fopen(cfg.out_json.c_str(), "w");
  if (f != nullptr) {
    std::fprintf(f, "{\"model\": \"%s\", \"dof\": %u, \"period_us\": 1000, \"cycles\": %d, \"substeps\": %d, "
                    "\"step_us\": {\"p50\": %.1f, \"p99\": %.1f, \"max\": %.1f}, \"joint0\": \"%s\", \"joint0_moved_rad\": %.4f}\n",
                 cfg.model_path, dof, cycles, backend.substeps(), p50, p99, mx, backend.joint_name(0).c_str(), moved);
    std::fclose(f);
  }

  if (g_fail_count == 0) {
    std::puts("OK: mujoco_backend");
    return 0;
  }
  std::printf("FAILED: %d checks\n", g_fail_count);
  return 1;
}
