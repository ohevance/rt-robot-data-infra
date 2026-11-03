// ===========================================================================
// 파일 역할 : MujocoBackend 구현. 자세한 설명은 mujoco_backend.hpp 머리글.
//
// MuJoCo 용어 (처음 보는 분을 위해)
//   mjModel : 로봇의 "설계도" (관절·링크·액추에이터·물리 상수). 읽기 전용. mj_loadXML 로 만든다
//   mjData  : 지금 이 순간의 "상태" (qpos 위치, qvel 속도, ctrl 명령, 접촉 ...). mj_step 이 한 걸음 진행시킨다
//   qpos    : 일반화 좌표(관절 각) 배열. 관절 j 의 값은 qpos[jnt_qposadr[j]]
//   qvel    : 일반화 속도 배열.          관절 j 의 값은 qvel[jnt_dofadr[j]]
//   ctrl    : 액추에이터 입력 배열. position 액추에이터는 "원하는 관절 각"을 넣으면 kp 로 끌어당긴다
// ===========================================================================
#include "rt_core/mujoco_backend.hpp"

#include <cmath>
#include <cstdio>

#include <mujoco/mujoco.h>

namespace rt_core {

MujocoBackend::MujocoBackend() {
  for (std::uint32_t i = 0; i < kMaxJoints; ++i) {
    joint_id_[i] = -1;
    qpos_adr_[i] = -1;
    dof_adr_[i] = -1;
    actuator_id_[i] = -1;
  }
}

MujocoBackend::~MujocoBackend() {
  if (data_ != nullptr) {
    mj_deleteData(data_);
    data_ = nullptr;
  }
  if (model_ != nullptr) {
    mj_deleteModel(model_);
    model_ = nullptr;
  }
}

void MujocoBackend::set_model(const std::string& xml_path) { xml_path_ = xml_path; }

void MujocoBackend::set_joint_names(const std::vector<std::string>& names) { joint_names_ = names; }

int MujocoBackend::model_nq() const {
  if (model_ == nullptr) {
    return 0;
  }
  return model_->nq;
}

int MujocoBackend::model_nu() const {
  if (model_ == nullptr) {
    return 0;
  }
  return model_->nu;
}

// ---------------------------------------------------------------------------
// init: 모델 로드 → 시뮬레이션 걸음 크기 맞추기 → 관절·액추에이터 연결 → 초기 상태. 전부 RT 스레드 밖에서.
bool MujocoBackend::init(std::uint32_t dof, std::int64_t period_ns) {
  if (dof == 0 || dof > kMaxJoints) {
    std::fprintf(stderr, "MujocoBackend: dof %u 는 1..%u 범위가 아님\n", dof, kMaxJoints);
    return false;
  }
  dof_ = dof;
  if (!load_model()) {
    return false;
  }
  tune_timestep(period_ns);

  bool ok = false;
  if (joint_names_.empty()) {
    ok = map_joints_in_order();
  } else {
    ok = map_joints_by_name();
  }
  if (ok) {
    ok = find_actuators();
  }
  if (!ok) {
    print_model_names();
    return false;
  }

  mj_forward(model_, data_);  // 초기 상태 계산 (위치 0 에서의 기구학 등). 첫 read_state 가 유효한 값을 돌려주게.
  print_mapping(period_ns);
  return true;
}

// 1) 모델 파일을 읽어 mjModel(설계도)·mjData(상태)를 만든다
bool MujocoBackend::load_model() {
  if (xml_path_.empty()) {
    std::fprintf(stderr, "MujocoBackend: 모델 파일이 지정되지 않음 (set_model)\n");
    return false;
  }
  char error[1000] = {0};
  model_ = mj_loadXML(xml_path_.c_str(), nullptr, error, sizeof(error));
  if (model_ == nullptr) {
    std::fprintf(stderr, "MujocoBackend: 모델 로드 실패 '%s': %s\n", xml_path_.c_str(), error);
    return false;
  }
  data_ = mj_makeData(model_);
  if (data_ == nullptr) {
    std::fprintf(stderr, "MujocoBackend: mj_makeData 실패\n");
    return false;
  }
  return true;
}

// 2) 시뮬레이션 걸음(timestep)을 제어 주기에 맞춘다.
//    제어 주기 1 ms, 모델 기본 걸음 2 ms 면 → 걸음 1 ms 로 줄여 주기마다 1번.
//    제어 주기 5 ms, 모델 걸음 2 ms 면    → 걸음 1.67 ms 로 맞춰 주기마다 3번.
//    (올림(ceil)을 쓰는 이유: 걸음은 모델이 정한 값보다 "작게"만 바꾼다. 키우면 물리가 불안정해진다)
void MujocoBackend::tune_timestep(std::int64_t period_ns) {
  double period_s = static_cast<double>(period_ns) / 1e9;
  double model_dt = model_->opt.timestep;
  int substeps = static_cast<int>(std::ceil(period_s / model_dt - 1e-9));
  if (substeps < 1) {
    substeps = 1;
  }
  substeps_ = substeps;
  sim_timestep_s_ = period_s / static_cast<double>(substeps);
  model_->opt.timestep = sim_timestep_s_;
}

// 연결 결과를 한 번 출력 (노드 로그·테스트 출력에서 "무엇 위에서 도는지" 보이게)
void MujocoBackend::print_mapping(std::int64_t period_ns) const {
  double period_s = static_cast<double>(period_ns) / 1e9;
  std::printf("MujocoBackend: '%s' nq=%d nu=%d, 제어 주기 %.3f ms = mj_step %d번 x %.3f ms\n", xml_path_.c_str(),
              model_->nq, model_->nu, period_s * 1000.0, substeps_, sim_timestep_s_ * 1000.0);
  for (std::uint32_t i = 0; i < dof_; ++i) {
    const char* act_name = mj_id2name(model_, mjOBJ_ACTUATOR, actuator_id_[i]);
    if (act_name == nullptr) {
      act_name = "(이름없음)";
    }
    std::printf("  관절 %u: %s (joint %d, qpos[%d], actuator %d '%s')\n", i, joint_names_[i].c_str(), joint_id_[i],
                qpos_adr_[i], actuator_id_[i], act_name);
  }
}

// 이름으로 관절을 찾는다. 하나라도 없으면 실패.
bool MujocoBackend::map_joints_by_name() {
  if (joint_names_.size() != dof_) {
    std::fprintf(stderr, "MujocoBackend: 관절 이름 %zu개 != dof %u\n", joint_names_.size(), dof_);
    return false;
  }
  for (std::uint32_t i = 0; i < dof_; ++i) {
    int id = mj_name2id(model_, mjOBJ_JOINT, joint_names_[i].c_str());
    if (id < 0) {
      std::fprintf(stderr, "MujocoBackend: 모델에 관절 '%s' 가 없음\n", joint_names_[i].c_str());
      return false;
    }
    joint_id_[i] = id;
    qpos_adr_[i] = model_->jnt_qposadr[id];
    dof_adr_[i] = model_->jnt_dofadr[id];
  }
  return true;
}

// 이름이 없으면 모델의 회전(hinge)·직선(slide) 관절을 앞에서부터 dof 개 쓴다. (자유 관절·볼 관절은 건너뜀)
bool MujocoBackend::map_joints_in_order() {
  joint_names_.clear();
  std::uint32_t count = 0;
  for (int id = 0; id < model_->njnt && count < dof_; ++id) {
    int type = model_->jnt_type[id];
    if (type != mjJNT_HINGE && type != mjJNT_SLIDE) {
      continue;
    }
    joint_id_[count] = id;
    qpos_adr_[count] = model_->jnt_qposadr[id];
    dof_adr_[count] = model_->jnt_dofadr[id];
    const char* name = mj_id2name(model_, mjOBJ_JOINT, id);
    if (name == nullptr) {
      name = "(이름 없음)";
    }
    joint_names_.push_back(name);
    count = count + 1;
  }
  if (count < dof_) {
    std::fprintf(stderr, "MujocoBackend: 모델에 1축 관절이 %u개뿐 (dof %u 필요)\n", count, dof_);
    return false;
  }
  return true;
}

// 관절마다 "그 관절에 붙은" 액추에이터를 찾는다. 없으면 그 관절을 움직일 방법이 없으므로 실패.
bool MujocoBackend::find_actuators() {
  for (std::uint32_t i = 0; i < dof_; ++i) {
    int found = -1;
    for (int a = 0; a < model_->nu; ++a) {
      bool drives_a_joint = (model_->actuator_trntype[a] == mjTRN_JOINT);
      bool drives_this_joint = (model_->actuator_trnid[2 * a] == joint_id_[i]);
      if (drives_a_joint && drives_this_joint) {
        found = a;
        break;
      }
    }
    if (found < 0) {
      std::fprintf(stderr, "MujocoBackend: 관절 '%s' 를 움직이는 액추에이터가 모델에 없음\n", joint_names_[i].c_str());
      return false;
    }
    actuator_id_[i] = found;
  }
  return true;
}

void MujocoBackend::print_model_names() const {
  if (model_ == nullptr) {
    return;
  }
  std::fprintf(stderr, "  모델의 관절 (%d개):", model_->njnt);
  for (int id = 0; id < model_->njnt; ++id) {
    const char* name = mj_id2name(model_, mjOBJ_JOINT, id);
    std::fprintf(stderr, " %s", name ? name : "(이름없음)");
  }
  std::fprintf(stderr, "\n  모델의 액추에이터 (%d개):", model_->nu);
  for (int a = 0; a < model_->nu; ++a) {
    const char* name = mj_id2name(model_, mjOBJ_ACTUATOR, a);
    std::fprintf(stderr, " %s", name ? name : "(이름없음)");
  }
  std::fprintf(stderr, "\n  → robots/*.yaml 의 mujoco.joints 를 위 관절 이름으로 맞추세요\n");
}

// ---------------------------------------------------------------------------
// RT 스레드, 매 주기: 목표를 ctrl 에 넣고 한 주기만큼 물리를 진행한다
void MujocoBackend::write_command(const double* target_position, std::uint32_t dof) {
  if (model_ == nullptr || data_ == nullptr) {
    return;
  }
  if (dof > dof_) {
    dof = dof_;
  }
  for (std::uint32_t i = 0; i < dof; ++i) {
    data_->ctrl[actuator_id_[i]] = target_position[i];
  }
  for (int s = 0; s < substeps_; ++s) {
    mj_step(model_, data_);
  }
}

// RT 스레드, 매 주기: 관절 위치·속도를 읽는다
void MujocoBackend::read_state(double* position, double* velocity, std::uint32_t dof) {
  if (model_ == nullptr || data_ == nullptr) {
    return;
  }
  if (dof > dof_) {
    dof = dof_;
  }
  for (std::uint32_t i = 0; i < dof; ++i) {
    position[i] = data_->qpos[qpos_adr_[i]];
    velocity[i] = data_->qvel[dof_adr_[i]];
  }
}

}  // namespace rt_core
