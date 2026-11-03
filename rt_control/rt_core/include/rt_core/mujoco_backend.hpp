#pragma once
// ===========================================================================
// 파일 역할 : MuJoCo 시뮬레이터를 "로봇"으로 쓰는 백엔드. SimLagBackend 와 같은 자리에 꽂힌다.
//
//   ControlStep ──write_command(목표 위치)──▶ MujocoBackend: ctrl[액추에이터] = 목표 → mj_step × substeps
//   ControlStep ◀──read_state(위치·속도)──── MujocoBackend: qpos / qvel 에서 읽는다
//
// 왜 필요한가
//   SimLag 는 "목표를 천천히 따라간다"만 흉내 낸다. MuJoCo 는 관절 한계·중력·접촉·모터 특성이 있는 진짜 물리 →
//   같은 제어 코드가 물리 모델 위에서도 1 kHz 를 지키는지(한 주기 안에 mj_step 이 끝나는지) 확인할 수 있다.
//
// 모델과 관절의 연결
//   - 모델 파일(xml)은 init 전에 set_model() 로 준다 (MuJoCo Menagerie 의 SO-ARM100 등)
//   - 관절 이름 목록을 set_joint_names() 로 주면 그 이름으로 찾고, 안 주면 모델의 관절을 앞에서부터 dof 개 쓴다
//   - 관절마다 그 관절을 움직이는 액추에이터(position 타입)를 찾아 둔다. 없으면 init 실패 (이유를 출력)
//
// RT 규칙
//   - 모델 로드·메모리 할당은 init() 안에서만 (RT 스레드 밖). write/read 는 할당·락·파일 없음
//   - mj_step 은 mjData 안의 미리 잡아 둔 메모리만 쓴다 (할당 없음) → RT 스레드에서 불러도 된다
//
// 빌드: cmake -DRT_CORE_WITH_MUJOCO=ON -DMUJOCO_DIR=<mujoco 설치 경로>  (scripts/get_mujoco.sh 가 받아 준다)
// 읽는 순서: set_model → init (load_model → tune_timestep → map_joints_* → find_actuators) → write_command → read_state → 소멸자
// ===========================================================================
#include <cstdint>
#include <string>
#include <vector>

#include "rt_core/backend.hpp"
#include "rt_core/joint_types.hpp"

// MuJoCo 의 구조체를 여기서는 이름만 안다 (헤더를 쓰는 쪽이 mujoco.h 를 몰라도 되게). 실제 정의는 .cpp 에서.
struct mjModel_;
struct mjData_;

namespace rt_core {

class MujocoBackend : public Backend {
 public:
  MujocoBackend();
  ~MujocoBackend() override;

  // init 전에 부른다
  void set_model(const std::string& xml_path);
  void set_joint_names(const std::vector<std::string>& names);

  bool init(std::uint32_t dof, std::int64_t period_ns) override;
  void write_command(const double* target_position, std::uint32_t dof) override;
  void read_state(double* position, double* velocity, std::uint32_t dof) override;

  // 확인용 (테스트·노드 상태 출력)
  int substeps() const { return substeps_; }
  double sim_timestep_s() const { return sim_timestep_s_; }
  const std::string& joint_name(std::uint32_t i) const { return joint_names_[i]; }
  int model_nq() const;
  int model_nu() const;

 private:
  bool load_model();
  void tune_timestep(std::int64_t period_ns);
  void print_mapping(std::int64_t period_ns) const;
  bool map_joints_by_name();
  bool map_joints_in_order();
  bool find_actuators();
  void print_model_names() const;

  std::string xml_path_;
  std::vector<std::string> joint_names_;   // 비어 있으면 모델 순서대로

  mjModel_* model_ = nullptr;
  mjData_* data_ = nullptr;
  std::uint32_t dof_ = 0;
  int substeps_ = 1;                       // 제어 한 주기에 mj_step 을 몇 번 하나
  double sim_timestep_s_ = 0.0;

  int joint_id_[kMaxJoints];               // 관절 i → MuJoCo 관절 번호
  int qpos_adr_[kMaxJoints];               // 관절 i → qpos 배열 위치
  int dof_adr_[kMaxJoints];                // 관절 i → qvel 배열 위치
  int actuator_id_[kMaxJoints];            // 관절 i → ctrl 배열 위치 (액추에이터 번호)
};

}  // namespace rt_core
