// ===========================================================================
// 파일 역할 : rt_core 를 감싸는 얇은 ZeroMQ 노드 (rt_zmq_node). ROS 2 노드(ros2_adapter)와 같은 rt_core 를 쓰고,
//            껍질만 ROS 2 → ZeroMQ 로 바꿨다. "미들웨어 교체 = 어댑터 교체" (docs/ARCHITECTURE.md) 를 코드로 보인 것.
//
//   소켓 (ZeroMQ C API, libzmq 4.3)
//     PUB    state_ep (기본 tcp://*:5555)  : STATE 패킷. publish_hz 로 솎아서 (1000 이면 RT 주기마다 하나씩 전부)
//     ROUTER cmd_ep   (기본 tcp://*:5556)  : 클라이언트(DEALER)가 TARGET·PING·GET_INFO 를 보내면 ACK·PONG·INFO 로 답한다
//   공유 메모리 (선택, 기본 /rt_state) : 같은 PC 의 다른 프로세스가 소켓 없이 "최신 상태 한 장"을 읽는다 (shm_seqlock.hpp)
//
//   스레드 3개 — ROS 2 노드와 같은 모양
//     RT 스레드    : RtLoop + ControlStep, 1 kHz, SCHED_FIFO. 소켓을 모른다
//     발행 스레드  : 상태 벨트(spsc_ring)를 비워 PUB 로 보내고 공유 메모리에 쓴다. pub_poll_us 마다 깬다
//     명령 스레드  : (main) ROUTER 를 zmq_poll 로 기다리다 패킷이 오면 검사 → 명령 우편함(spsc_ring) → ACK
//     ZeroMQ 소켓은 스레드 사이에 공유하지 않는다 — 소켓 하나는 스레드 하나만 만진다 (libzmq 의 규칙)
//
// 읽는 순서 : 1) Options / parse_args  2) main — 준비 → 스레드 시작 → 명령 루프 → 정리
//            3) handle_packet() — 패킷 하나에 대한 판정과 답 (거절 사유는 전부 ACK status 로 돌려주고 센다)
//            4) publisher_main() — 발행 스레드 본체
//
// 이 파일에는 제어 논리가 없다. 제어는 rt_core/control_step.cpp 에 있다.
// ===========================================================================
#include <atomic>
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include <time.h>
#include <zmq.h>

#include "rt_core/control_step.hpp"
#include "rt_core/robot_state_machine.hpp"
#include "rt_core/rt_clock.hpp"
#include "rt_core/rt_loop.hpp"
#include "rt_core/shm_seqlock.hpp"
#include "rt_core/sim_lag_backend.hpp"
#include "rt_core/wire.hpp"
#ifdef RT_CORE_WITH_MUJOCO
#include "rt_core/mujoco_backend.hpp"
#endif

using namespace rt_core;

// 링 버퍼들은 크기가 커서 전역(정적)에 둔다 (ROS 2 노드와 같다)
static CommandRing g_cmd_ring;                         // 명령 스레드 → RT
static StateRing g_state_ring;                         // RT → 발행 스레드
static SpscRing<Sample, kRingSize> g_timing_ring;      // RT 루프 타이밍 → 발행 스레드
static std::atomic<bool> g_stop{false};

static void on_signal(int) { g_stop.store(true); }

// ---------------------------------------------------------------------------
// 1) 옵션
// ---------------------------------------------------------------------------
struct Options {
  std::uint32_t dof = 6;
  int loop_hz = 1000;
  int publish_hz = 100;          // STATE 를 몇 Hz 로 보낼까 (loop_hz 의 약수가 아니면 가까운 정수배로 솎는다)
  int prio = 80;                 // SCHED_FIFO 우선순위. 0 = 일반 스케줄링 (권한 없는 곳·시험)
  int cpu = -1;
  int watchdog_ms = 50;
  double max_step_rad = 0.05;
  double sim_tau_s = 0.05;
  std::string backend = "sim_lag";
  std::string mujoco_model;
  std::string state_ep = "tcp://*:5555";
  std::string cmd_ep = "tcp://*:5556";
  std::string shm_name = "/rt_state";   // "" 이면 공유 메모리를 쓰지 않는다
  int pub_poll_us = 200;         // 발행 스레드가 벨트를 비우러 깨는 간격 (상태가 소켓에 실리기까지 더해지는 최대 지연)
  double seconds = 0.0;          // 0 = 신호(Ctrl+C, SIGTERM)가 올 때까지
  std::string status_json;       // 끝날 때 센 값들을 이 파일에 (시험·측정용)
};

static void usage() {
  std::printf(
      "rt_zmq_node — rt_core 를 ZeroMQ 로 감싼 노드\n"
      "  --dof N (6)  --loop-hz N (1000)  --publish-hz N (100)  --prio N (80, 0=일반)  --cpu N (-1)\n"
      "  --watchdog-ms N (50)  --max-step-rad X (0.05)  --sim-tau X (0.05)  --backend sim_lag|mujoco  --mujoco-model PATH\n"
      "  --state-ep EP (tcp://*:5555)  --cmd-ep EP (tcp://*:5556)  --shm NAME (/rt_state, \"\" = 끔)\n"
      "  --pub-poll-us N (200)  --seconds X (0 = 신호까지)  --status-json PATH\n");
}

static bool parse_args(int argc, char** argv, Options& o) {
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "-h" || a == "--help") {
      usage();
      std::exit(0);
    }
    if (i + 1 >= argc) {
      std::fprintf(stderr, "값이 없음: %s\n", a.c_str());
      return false;
    }
    std::string v = argv[++i];
    if (a == "--dof") o.dof = static_cast<std::uint32_t>(std::atoi(v.c_str()));
    else if (a == "--loop-hz") o.loop_hz = std::atoi(v.c_str());
    else if (a == "--publish-hz") o.publish_hz = std::atoi(v.c_str());
    else if (a == "--prio") o.prio = std::atoi(v.c_str());
    else if (a == "--cpu") o.cpu = std::atoi(v.c_str());
    else if (a == "--watchdog-ms") o.watchdog_ms = std::atoi(v.c_str());
    else if (a == "--max-step-rad") o.max_step_rad = std::atof(v.c_str());
    else if (a == "--sim-tau") o.sim_tau_s = std::atof(v.c_str());
    else if (a == "--backend") o.backend = v;
    else if (a == "--mujoco-model") o.mujoco_model = v;
    else if (a == "--state-ep") o.state_ep = v;
    else if (a == "--cmd-ep") o.cmd_ep = v;
    else if (a == "--shm") o.shm_name = v;
    else if (a == "--pub-poll-us") o.pub_poll_us = std::atoi(v.c_str());
    else if (a == "--seconds") o.seconds = std::atof(v.c_str());
    else if (a == "--status-json") o.status_json = v;
    else {
      std::fprintf(stderr, "모르는 옵션: %s\n", a.c_str());
      return false;
    }
  }
  if (o.dof == 0 || o.dof > kMaxJoints || o.loop_hz <= 0 || o.publish_hz <= 0 || o.publish_hz > o.loop_hz) {
    std::fprintf(stderr, "값 범위: 1 <= dof <= %u, 0 < publish_hz <= loop_hz\n", kMaxJoints);
    return false;
  }
  return true;
}

// 노드가 센 값. 명령 스레드만 쓰는 것은 일반 정수, 두 스레드가 만지는 것은 atomic
struct NodeCounters {
  std::uint64_t packets = 0;
  std::uint64_t targets_ok = 0;
  std::uint64_t rejected[6] = {0, 0, 0, 0, 0, 0};  // AckStatus 별 (OK 칸은 쓰지 않음)
  std::uint64_t pings = 0;
  std::uint64_t infos = 0;
  std::atomic<std::uint64_t> states_sent{0};
  std::atomic<std::uint64_t> states_send_dropped{0};  // PUB 가 받지 않음 (EAGAIN — 구독자가 밀려 높은 물 표시에 닿음)
  std::atomic<std::uint64_t> shm_writes{0};
  std::atomic<std::int64_t> wake_max_ns{0};
  std::atomic<std::uint64_t> wake_over_period{0};     // 깨어남 지연이 한 주기를 넘은 횟수
};

static int set_int(void* sock, int opt, int value) { return zmq_setsockopt(sock, opt, &value, sizeof(value)); }

// ---------------------------------------------------------------------------
// 4) 발행 스레드: 벨트를 비워 STATE 를 보내고, 공유 메모리에 최신 한 장을 쓴다
// ---------------------------------------------------------------------------
static void publisher_main(void* pub, ShmSegment<JointStateSample>* shm, const Options& o, NodeCounters& nc) {
  const std::uint64_t decim = static_cast<std::uint64_t>(o.loop_hz / o.publish_hz);  // 1 kHz / 100 Hz = 10 주기마다 하나
  std::uint8_t buf[wire::kMaxPacket];
  std::uint32_t seq = 0;
  const std::int64_t period_ns = 1000000000LL / o.loop_hz;
  timespec nap;
  nap.tv_sec = 0;
  nap.tv_nsec = static_cast<long>(o.pub_poll_us) * 1000L;

  while (!g_stop.load(std::memory_order_relaxed)) {
    JointStateSample s;
    JointStateSample latest;
    bool got = false;
    while (g_state_ring.pop(s)) {
      latest = s;
      got = true;
      if (s.iter % decim != 0) {
        continue;
      }
      seq = seq + 1;
      std::size_t n = wire::encode_state(buf, sizeof(buf), seq, now_ns(), s);
      if (zmq_send(pub, buf, n, ZMQ_DONTWAIT) < 0) {
        nc.states_send_dropped.fetch_add(1, std::memory_order_relaxed);
      } else {
        nc.states_sent.fetch_add(1, std::memory_order_relaxed);
      }
    }
    if (got && shm != nullptr) {
      shm->write(latest);
      nc.shm_writes.fetch_add(1, std::memory_order_relaxed);
    }
    Sample t;
    while (g_timing_ring.pop(t)) {  // 타이밍 벨트도 비운다 (안 비우면 차서 timing_drops 가 오른다)
      if (t.wake_lat_ns > nc.wake_max_ns.load(std::memory_order_relaxed)) {
        nc.wake_max_ns.store(t.wake_lat_ns, std::memory_order_relaxed);
      }
      if (t.wake_lat_ns > period_ns) {
        nc.wake_over_period.fetch_add(1, std::memory_order_relaxed);
      }
    }
    nanosleep(&nap, nullptr);
  }
}

// ---------------------------------------------------------------------------
// 3) 패킷 하나에 대한 답. 답 패킷을 reply 에 쓰고 길이를 돌려준다 (0 = 답하지 않음)
// ---------------------------------------------------------------------------
static std::size_t handle_packet(const std::uint8_t* p, std::size_t len, const Options& o, const std::string& info_json,
                                 std::uint32_t& out_seq, NodeCounters& nc, std::uint8_t* reply, std::size_t cap) {
  nc.packets = nc.packets + 1;
  out_seq = out_seq + 1;
  wire::Header h;
  wire::WireError e = wire::decode_header(p, len, h);
  if (e != wire::WireError::OK) {
    nc.rejected[static_cast<int>(wire::AckStatus::BAD_PACKET)] += 1;
    // 머리를 못 읽었으면 seq 도 믿을 수 없다 → acked_seq 0 으로 답한다 (클라이언트는 "형식 오류"만 안다)
    return wire::encode_ack(reply, cap, out_seq, now_ns(), 0, wire::AckStatus::BAD_PACKET);
  }

  switch (h.type) {
    case wire::MsgType::TARGET: {
      JointCommand cmd;
      bool bad_value = false;
      e = wire::decode_target(p, len, h, cmd, bad_value);
      wire::AckStatus st = wire::AckStatus::OK;
      if (e == wire::WireError::BAD_DOF || (e == wire::WireError::OK && cmd.dof != o.dof)) {
        st = wire::AckStatus::BAD_DOF;
      } else if (e != wire::WireError::OK) {
        st = wire::AckStatus::BAD_PACKET;
      } else if (bad_value) {
        st = wire::AckStatus::BAD_VALUE;
      } else {
        cmd.stamp_ns = now_ns();
        if (!g_cmd_ring.push(cmd)) {
          st = wire::AckStatus::RING_FULL;  // RT 스레드가 우편함을 비우지 못한다 (정상이면 0)
        }
      }
      if (st == wire::AckStatus::OK) {
        nc.targets_ok = nc.targets_ok + 1;
      } else {
        nc.rejected[static_cast<int>(st)] += 1;
      }
      return wire::encode_ack(reply, cap, out_seq, now_ns(), h.seq, st);
    }
    case wire::MsgType::PING:
      nc.pings = nc.pings + 1;
      // PONG 은 PING 의 seq 와 stamp_ns 를 그대로 돌려준다 → 클라이언트가 자기 시계 하나로 왕복을 잰다
      return wire::encode_simple(reply, cap, wire::MsgType::PONG, h.seq, h.stamp_ns);
    case wire::MsgType::GET_INFO:
      nc.infos = nc.infos + 1;
      return wire::encode_simple(reply, cap, wire::MsgType::INFO, h.seq, now_ns(),
                                 reinterpret_cast<const std::uint8_t*>(info_json.data()), info_json.size());
    default:
      nc.rejected[static_cast<int>(wire::AckStatus::UNKNOWN_TYPE)] += 1;
      return wire::encode_ack(reply, cap, out_seq, now_ns(), h.seq, wire::AckStatus::UNKNOWN_TYPE);
  }
}

static std::unique_ptr<Backend> make_backend(const Options& o) {
  if (o.backend == "sim_lag") {
    return std::unique_ptr<Backend>(new SimLagBackend(o.sim_tau_s));
  }
#ifdef RT_CORE_WITH_MUJOCO
  if (o.backend == "mujoco") {
    MujocoBackend* m = new MujocoBackend();
    m->set_model(o.mujoco_model);
    return std::unique_ptr<Backend>(m);
  }
#endif
  std::fprintf(stderr, "backend '%s' 를 만들 수 없음 (mujoco 는 -DRT_CORE_WITH_MUJOCO=ON 빌드에서만)\n", o.backend.c_str());
  return nullptr;
}

static void write_status_json(const Options& o, const NodeCounters& nc, const ControlCounters& cc, const RtLoop& loop,
                              std::uint64_t timing_drops) {
  if (o.status_json.empty()) {
    return;
  }
  const RtStatus& st = loop.status();
  FILE* f = std::fopen(o.status_json.c_str(), "w");
  if (f == nullptr) {
    return;
  }
  std::fprintf(f,
               "{\"packets\": %llu, \"targets_ok\": %llu, \"rejected\": {\"bad_dof\": %llu, \"ring_full\": %llu, "
               "\"bad_packet\": %llu, \"unknown_type\": %llu, \"bad_value\": %llu}, \"pings\": %llu, \"infos\": %llu, "
               "\"commands_applied\": %llu, \"states_sent\": %llu, \"states_send_dropped\": %llu, \"shm_writes\": %llu, "
               "\"state_drops\": %llu, \"timing_drops\": %llu, \"watchdog_trips\": %llu, \"illegal_events\": %llu, "
               "\"robot_state\": \"%s\", \"wake_max_us\": %.1f, \"wake_over_period\": %llu, "
               "\"rt\": {\"sched_fifo\": %s, \"mlockall\": %s, \"kernel_realtime\": %s}}\n",
               static_cast<unsigned long long>(nc.packets), static_cast<unsigned long long>(nc.targets_ok),
               static_cast<unsigned long long>(nc.rejected[1]), static_cast<unsigned long long>(nc.rejected[2]),
               static_cast<unsigned long long>(nc.rejected[3]), static_cast<unsigned long long>(nc.rejected[4]),
               static_cast<unsigned long long>(nc.rejected[5]), static_cast<unsigned long long>(nc.pings),
               static_cast<unsigned long long>(nc.infos), static_cast<unsigned long long>(cc.commands_applied.load()),
               static_cast<unsigned long long>(nc.states_sent.load()),
               static_cast<unsigned long long>(nc.states_send_dropped.load()),
               static_cast<unsigned long long>(nc.shm_writes.load()), static_cast<unsigned long long>(cc.state_drops.load()),
               static_cast<unsigned long long>(timing_drops), static_cast<unsigned long long>(cc.watchdog_trips.load()),
               static_cast<unsigned long long>(cc.illegal_events.load()),
               robot_state_name(static_cast<RobotState>(cc.robot_state.load())),
               static_cast<double>(nc.wake_max_ns.load()) / 1000.0,
               static_cast<unsigned long long>(nc.wake_over_period.load()), st.rt_sched_ok ? "true" : "false",
               st.mlock_ok ? "true" : "false", st.kernel_realtime ? "true" : "false");
  std::fclose(f);
}

// ---------------------------------------------------------------------------
// 2) main
// ---------------------------------------------------------------------------
int main(int argc, char** argv) {
  Options o;
  if (!parse_args(argc, argv, o)) {
    usage();
    return 2;
  }
  std::signal(SIGINT, on_signal);
  std::signal(SIGTERM, on_signal);

  // ---- 로봇 쪽: 백엔드 → 제어 단계 → RT 루프 (ROS 2 노드와 같은 조립) ----
  std::unique_ptr<Backend> backend = make_backend(o);
  if (backend == nullptr) {
    return 2;
  }
  RtConfig rt_cfg;
  rt_cfg.period_ns = 1000000000LL / o.loop_hz;
  rt_cfg.prio = o.prio;
  rt_cfg.cpu = o.cpu;
  rt_cfg.seconds = 0.0;  // RT 루프는 g_stop 으로 멈춘다
  if (!backend->init(o.dof, rt_cfg.period_ns)) {
    std::fprintf(stderr, "backend init 실패\n");
    return 2;
  }
  ControlConfig ctl;
  ctl.dof = o.dof;
  ctl.period_ns = rt_cfg.period_ns;
  ctl.watchdog_ns = static_cast<std::int64_t>(o.watchdog_ms) * 1000000LL;
  ctl.max_step_rad = o.max_step_rad;
  ctl.recover_cycles = static_cast<std::uint32_t>(o.loop_hz / 10);  // 100 ms 연속 정상이면 READY
  ControlCounters cc;
  ControlStep control(ctl, *backend, g_cmd_ring, g_state_ring, cc);
  RtLoop loop(rt_cfg);

  // ---- 소켓 ----
  void* ctx = zmq_ctx_new();
  void* pub = zmq_socket(ctx, ZMQ_PUB);
  void* router = zmq_socket(ctx, ZMQ_ROUTER);
  set_int(pub, ZMQ_LINGER, 0);
  set_int(router, ZMQ_LINGER, 0);
  set_int(pub, ZMQ_SNDHWM, 1000);  // 구독자 하나당 1,000개(1 kHz 에서 1초)까지 쌓고, 넘으면 버린다 — 느린 구독자가 노드를 막지 않게
  if (zmq_bind(pub, o.state_ep.c_str()) != 0 || zmq_bind(router, o.cmd_ep.c_str()) != 0) {
    std::fprintf(stderr, "bind 실패: %s (state %s, cmd %s)\n", zmq_strerror(zmq_errno()), o.state_ep.c_str(), o.cmd_ep.c_str());
    return 3;
  }

  // ---- 공유 메모리 (선택) ----
  std::unique_ptr<ShmSegment<JointStateSample>> shm;
  if (!o.shm_name.empty()) {
    shm.reset(new ShmSegment<JointStateSample>());
    if (!shm->create(o.shm_name, rt_cfg.period_ns)) {
      std::fprintf(stderr, "공유 메모리 %s 를 만들 수 없음 (errno %d) — 끄고 계속\n", o.shm_name.c_str(), shm->error());
      shm.reset();
    }
  }

  // ---- 스레드 시작: RT → 발행 ----
  std::atomic<std::uint64_t> timing_drops{0};
  NodeCounters nc;
  std::thread rt_thread([&]() { loop.run(control, g_timing_ring, timing_drops, &g_stop); });
  std::thread pub_thread([&]() { publisher_main(pub, shm.get(), o, nc); });

  // INFO 는 RT 스레드가 스케줄 결과를 적은 뒤에 만든다 (잠깐 기다림)
  timespec wait_rt = {0, 50 * 1000 * 1000};
  nanosleep(&wait_rt, nullptr);
  const RtStatus& rs = loop.status();
  int zmq_major = 0, zmq_minor = 0, zmq_patch = 0;
  zmq_version(&zmq_major, &zmq_minor, &zmq_patch);
  char info[768];
  std::snprintf(info, sizeof(info),
                "{\"node\": \"rt_zmq_node\", \"protocol_version\": %u, \"dof\": %u, \"loop_hz\": %d, \"publish_hz\": %d, "
                "\"backend\": \"%s\", \"watchdog_ms\": %d, \"max_step_rad\": %.3f, \"shm\": \"%s\", "
                "\"rt\": {\"sched_fifo\": %s, \"mlockall\": %s, \"kernel_realtime\": %s, \"kernel\": \"%s\"}, \"zmq\": \"%d.%d.%d\"}",
                static_cast<unsigned>(wire::kVersion), o.dof, o.loop_hz, o.publish_hz, o.backend.c_str(), o.watchdog_ms,
                o.max_step_rad, shm ? o.shm_name.c_str() : "", rs.rt_sched_ok ? "true" : "false",
                rs.mlock_ok ? "true" : "false", rs.kernel_realtime ? "true" : "false", rs.kernel_release.c_str(),
                zmq_major, zmq_minor, zmq_patch);
  const std::string info_json = info;
  std::fprintf(stderr, "rt_zmq_node: %s\n", info_json.c_str());

  // ---- 명령 루프 (main 스레드) ----
  const std::int64_t end_ns = (o.seconds > 0.0) ? now_ns() + static_cast<std::int64_t>(o.seconds * 1e9) : 0;
  std::uint32_t out_seq = 0;
  std::uint8_t idbuf[256];
  std::uint8_t in[wire::kMaxPacket + 64];
  std::uint8_t reply[1024];
  while (!g_stop.load()) {
    if (end_ns != 0 && now_ns() >= end_ns) {
      break;
    }
    zmq_pollitem_t item = {router, 0, ZMQ_POLLIN, 0};
    int rc = zmq_poll(&item, 1, 100);  // 100 ms 마다 한 번은 깨어 종료를 확인한다
    if (rc <= 0 || !(item.revents & ZMQ_POLLIN)) {
      continue;
    }
    // ROUTER 는 [보낸 쪽 이름][본문] 두 조각으로 받는다 (DEALER 가 보낸 경우)
    int id_len = zmq_recv(router, idbuf, sizeof(idbuf), ZMQ_DONTWAIT);
    if (id_len < 0) {
      continue;
    }
    int more = 0;
    std::size_t more_len = sizeof(more);
    zmq_getsockopt(router, ZMQ_RCVMORE, &more, &more_len);
    if (!more) {
      continue;  // 본문이 없는 이상한 메시지
    }
    int n = zmq_recv(router, in, sizeof(in), 0);
    // 남은 조각이 있으면 버린다 (한 메시지 = 한 패킷이 규칙)
    zmq_getsockopt(router, ZMQ_RCVMORE, &more, &more_len);
    while (more) {
      std::uint8_t junk[64];
      zmq_recv(router, junk, sizeof(junk), 0);
      zmq_getsockopt(router, ZMQ_RCVMORE, &more, &more_len);
      n = -1;
    }
    std::size_t len = (n < 0) ? 0 : static_cast<std::size_t>(n);
    if (n > static_cast<int>(sizeof(in))) {
      len = 0;  // zmq_recv 는 버퍼보다 큰 메시지를 잘라서 넣고 원래 길이를 돌려준다 → 형식 오류로 처리
    }
    std::size_t rlen = handle_packet(in, len, o, info_json, out_seq, nc, reply, sizeof(reply));
    if (rlen > 0) {
      zmq_send(router, idbuf, static_cast<std::size_t>(id_len), ZMQ_SNDMORE | ZMQ_DONTWAIT);
      zmq_send(router, reply, rlen, ZMQ_DONTWAIT);
    }
  }

  // ---- 정리: 멈춤 신호 → 스레드 합류 → 센 값 기록 → 소켓 닫기 ----
  g_stop.store(true);
  rt_thread.join();
  pub_thread.join();
  write_status_json(o, nc, cc, loop, timing_drops.load());
  if (shm) {
    shm->close();
  }
  zmq_close(pub);
  zmq_close(router);
  zmq_ctx_term(ctx);
  std::fprintf(stderr, "rt_zmq_node: 끝 (패킷 %llu, 명령 %llu, 상태 %llu)\n", static_cast<unsigned long long>(nc.packets),
               static_cast<unsigned long long>(nc.targets_ok), static_cast<unsigned long long>(nc.states_sent.load()));
  return 0;
}
