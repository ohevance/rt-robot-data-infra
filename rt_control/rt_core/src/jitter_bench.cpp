// ===========================================================================
// 파일 역할 : jitter_bench — RT 루프가 주기를 얼마나 정확히 지키는지 재는 측정기 (실행 파일)
//
// 읽는 순서 : 1) main()            — 전체 흐름 (약 40줄)
//            2) parse_args()      — 명령줄 옵션 읽기
//            3) compute_stats()   — min / avg / p50 / p99 / p99.9 / max
//            4) print_report()    — 화면 출력
//            5) write_json() / write_csv()
//
// 구조 (스레드 2개)
//   [RT 스레드 = main 스레드 : RtLoop::run] --SPSC 링--> [로깅 스레드 : 값을 모아 두었다가 끝나면 통계]
//   RT 스레드는 파일을 전혀 만지지 않는다. 그것이 이 프로그램이 보여주려는 핵심이다.
//
// 사용 예
//   ./jitter_bench --seconds 60 --period-us 1000 --prio 80 --cpu 2 --label rt_idle --json out.json
//   ./jitter_bench --no-rt --seconds 10            (일반 스케줄링, 비교용)
// ===========================================================================
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

#include "rt_core/rt_loop.hpp"
#include "rt_core/spsc_ring.hpp"

using rt_core::kRingSize;
using rt_core::RtConfig;
using rt_core::RtLoop;
using rt_core::RtStatus;
using rt_core::Sample;

// 링 버퍼는 2 MB 라 스택에 두지 않고 전역(정적)으로 둔다.
static rt_core::SpscRing<Sample, kRingSize> g_ring;

// ---------------------------------------------------------------------------
// 명령줄 옵션
// ---------------------------------------------------------------------------
struct Options {
  RtConfig cfg;
  std::string label = "run";  // 결과에 붙일 이름 (예: rt_idle)
  std::string json_path;      // 비어 있으면 JSON 안 씀
  std::string csv_path;       // 비어 있으면 CSV 안 씀
};

static void print_usage() {
  std::puts(
      "jitter_bench [--period-us N] [--seconds S] [--prio P | --no-rt] [--cpu C] [--work-us W]\n"
      "             [--label NAME] [--json FILE] [--csv FILE]\n"
      "  --period-us  루프 주기 (기본 1000 = 1 kHz)\n"
      "  --seconds    측정 시간 (기본 10)\n"
      "  --prio       SCHED_FIFO 우선순위 1~99 (기본 80). --no-rt 는 일반 스케줄링\n"
      "  --cpu        고정할 CPU 번호 (기본 없음)\n"
      "  --work-us    매 주기 바쁘게 도는 시간 (기본 50)\n"
      "  --label      결과에 붙일 이름 (예: rt_idle, rt_stress, generic_idle)\n");
}

// 옵션 뒤에 오는 값 하나를 꺼낸다. 없으면 종료.
static std::string take_value(int argc, char** argv, int& i, const char* option_name) {
  if (i + 1 >= argc) {
    std::fprintf(stderr, "%s 뒤에 값이 없습니다\n", option_name);
    std::exit(2);
  }
  i = i + 1;
  return std::string(argv[i]);
}

static Options parse_args(int argc, char** argv) {
  Options o;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--period-us") {
      o.cfg.period_ns = std::stoll(take_value(argc, argv, i, "--period-us")) * 1000;
    } else if (a == "--seconds") {
      o.cfg.seconds = std::stod(take_value(argc, argv, i, "--seconds"));
    } else if (a == "--prio") {
      o.cfg.prio = std::stoi(take_value(argc, argv, i, "--prio"));
    } else if (a == "--no-rt") {
      o.cfg.prio = 0;
    } else if (a == "--cpu") {
      o.cfg.cpu = std::stoi(take_value(argc, argv, i, "--cpu"));
    } else if (a == "--work-us") {
      o.cfg.work_us = static_cast<std::uint32_t>(std::stoul(take_value(argc, argv, i, "--work-us")));
    } else if (a == "--label") {
      o.label = take_value(argc, argv, i, "--label");
    } else if (a == "--json") {
      o.json_path = take_value(argc, argv, i, "--json");
    } else if (a == "--csv") {
      o.csv_path = take_value(argc, argv, i, "--csv");
    } else if (a == "--help" || a == "-h") {
      print_usage();
      std::exit(0);
    } else {
      std::fprintf(stderr, "모르는 옵션: %s\n", a.c_str());
      print_usage();
      std::exit(2);
    }
  }

  // 말이 안 되는 설정은 여기서 막는다
  if (o.cfg.period_ns < 100000) {
    std::fprintf(stderr, "주기는 100 us 이상이어야 합니다\n");
    std::exit(2);
  }
  if (static_cast<std::int64_t>(o.cfg.work_us) * 1000 >= o.cfg.period_ns) {
    std::fprintf(stderr, "work-us 는 주기보다 작아야 합니다\n");
    std::exit(2);
  }
  return o;
}

// ---------------------------------------------------------------------------
// 통계
// ---------------------------------------------------------------------------
struct Stats {
  double min_us = 0, avg_us = 0, p50_us = 0, p99_us = 0, p999_us = 0, max_us = 0;
  std::size_t count = 0;
};

// 정렬된 배열에서 p 백분위수. p99.9 = "1,000개 중 999개는 이 값 이내"
static std::int64_t percentile(const std::vector<std::int64_t>& sorted, double p) {
  std::size_t n = sorted.size();
  std::size_t index = static_cast<std::size_t>(std::ceil(p / 100.0 * static_cast<double>(n)));
  if (index < 1) index = 1;
  if (index > n) index = n;
  return sorted[index - 1];
}

static Stats compute_stats(std::vector<std::int64_t> values_ns) {
  Stats s;
  if (values_ns.empty()) {
    return s;
  }
  std::sort(values_ns.begin(), values_ns.end());

  double sum = 0.0;
  for (std::size_t i = 0; i < values_ns.size(); ++i) {
    sum += static_cast<double>(values_ns[i]);
  }

  s.count = values_ns.size();
  s.min_us = static_cast<double>(values_ns.front()) / 1000.0;
  s.max_us = static_cast<double>(values_ns.back()) / 1000.0;
  s.avg_us = sum / static_cast<double>(values_ns.size()) / 1000.0;
  s.p50_us = static_cast<double>(percentile(values_ns, 50.0)) / 1000.0;
  s.p99_us = static_cast<double>(percentile(values_ns, 99.0)) / 1000.0;
  s.p999_us = static_cast<double>(percentile(values_ns, 99.9)) / 1000.0;
  return s;
}

// ---------------------------------------------------------------------------
// 출력
// ---------------------------------------------------------------------------
static const char* ok_or_error(bool ok, bool attempted, int err) {
  if (!attempted) return "off";
  if (ok) return "ok";
  return std::strerror(err);
}

static void print_row(const char* name, const Stats& s) {
  std::printf("| %-14s | %9.1f | %9.1f | %9.1f | %9.1f | %9.1f | %9.1f |\n", name, s.min_us, s.avg_us, s.p50_us,
              s.p99_us, s.p999_us, s.max_us);
}

static void print_report(const Options& o, const RtStatus& st, std::uint64_t iterations, std::size_t sample_count,
                         std::uint64_t drops, const Stats& wake, const Stats& period_err, const Stats& work) {
  const char* rt_kernel = "no";
  if (st.kernel_realtime) rt_kernel = "yes";

  std::printf("== rt_core jitter_bench : %s ==\n", o.label.c_str());
  std::printf("kernel: %s | PREEMPT_RT: %s | SCHED_FIFO: %s | mlockall: %s | cpu_pin: %s\n",
              st.kernel_release.c_str(), rt_kernel,
              ok_or_error(st.rt_sched_ok, o.cfg.prio > 0, st.rt_errno),
              ok_or_error(st.mlock_ok, true, st.mlock_errno),
              ok_or_error(st.affinity_ok, o.cfg.cpu >= 0, st.affinity_errno));
  std::printf("period: %lld us | duration: %.1f s | iterations: %llu | samples: %zu | drops: %llu\n",
              static_cast<long long>(o.cfg.period_ns / 1000), o.cfg.seconds,
              static_cast<unsigned long long>(iterations), sample_count, static_cast<unsigned long long>(drops));
  std::printf("| %-14s | %9s | %9s | %9s | %9s | %9s | %9s |  (us)\n", "metric", "min", "avg", "p50", "p99", "p99.9", "max");
  std::printf("|----------------|-----------|-----------|-----------|-----------|-----------|-----------|\n");
  print_row("wake latency", wake);
  print_row("period error", period_err);
  print_row("work time", work);
}

static void write_stats_json(std::FILE* f, const char* key, const Stats& s, bool last) {
  std::fprintf(f, "  \"%s\": {\"min\": %.3f, \"avg\": %.3f, \"p50\": %.3f, \"p99\": %.3f, \"p999\": %.3f, \"max\": %.3f, \"n\": %zu}",
               key, s.min_us, s.avg_us, s.p50_us, s.p99_us, s.p999_us, s.max_us, s.count);
  if (last) {
    std::fputs("\n", f);
  } else {
    std::fputs(",\n", f);
  }
}

static bool write_json(const Options& o, const RtStatus& st, std::uint64_t iterations, std::size_t sample_count,
                       std::uint64_t drops, const Stats& wake, const Stats& period_err, const Stats& work) {
  std::FILE* f = std::fopen(o.json_path.c_str(), "w");
  if (f == nullptr) {
    std::perror("json open");
    return false;
  }
  std::fprintf(f, "{\n");
  std::fprintf(f, "  \"label\": \"%s\",\n", o.label.c_str());
  std::fprintf(f, "  \"kernel\": \"%s\",\n", st.kernel_release.c_str());
  std::fprintf(f, "  \"preempt_rt\": %s,\n", st.kernel_realtime ? "true" : "false");
  std::fprintf(f, "  \"sched_fifo\": %s,\n", st.rt_sched_ok ? "true" : "false");
  std::fprintf(f, "  \"sched_errno\": %d,\n", st.rt_errno);
  std::fprintf(f, "  \"mlockall\": %s,\n", st.mlock_ok ? "true" : "false");
  std::fprintf(f, "  \"mlock_errno\": %d,\n", st.mlock_errno);
  std::fprintf(f, "  \"cpu_pin\": %d,\n", o.cfg.cpu);
  std::fprintf(f, "  \"period_us\": %lld,\n", static_cast<long long>(o.cfg.period_ns / 1000));
  std::fprintf(f, "  \"seconds\": %.3f,\n", o.cfg.seconds);
  std::fprintf(f, "  \"work_us\": %u,\n", o.cfg.work_us);
  std::fprintf(f, "  \"iterations\": %llu,\n", static_cast<unsigned long long>(iterations));
  std::fprintf(f, "  \"samples\": %zu,\n", sample_count);
  std::fprintf(f, "  \"drops\": %llu,\n", static_cast<unsigned long long>(drops));
  write_stats_json(f, "wake_us", wake, false);
  write_stats_json(f, "period_err_us", period_err, false);
  write_stats_json(f, "work_us_stats", work, true);
  std::fprintf(f, "}\n");
  std::fclose(f);
  std::printf("json -> %s\n", o.json_path.c_str());
  return true;
}

static void write_csv(const Options& o, const std::vector<Sample>& samples) {
  std::ofstream out(o.csv_path);
  out << "iter,wake_lat_ns,period_err_ns,work_ns\n";
  for (std::size_t i = 0; i < samples.size(); ++i) {
    const Sample& s = samples[i];
    out << s.iter << ',' << s.wake_lat_ns << ',' << s.period_err_ns << ',' << s.work_ns << '\n';
  }
  std::printf("csv  -> %s\n", o.csv_path.c_str());
}

// ---------------------------------------------------------------------------
// 로깅 스레드가 하는 일: 링에서 꺼내 벡터에 모은다. 비어 있으면 1 ms 쉰다.
// RT 스레드가 끝나면(running == false) 남은 것을 다 꺼내고 종료한다.
// ---------------------------------------------------------------------------
static void logger_thread_main(std::atomic<bool>* running, std::vector<Sample>* samples) {
  Sample s;
  while (true) {
    if (g_ring.pop(s)) {
      samples->push_back(s);
      continue;
    }
    if (!running->load(std::memory_order_acquire)) {
      while (g_ring.pop(s)) {
        samples->push_back(s);
      }
      return;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
int main(int argc, char** argv) {
  Options o = parse_args(argc, argv);

  std::atomic<std::uint64_t> drops{0};
  std::atomic<bool> running{true};
  std::vector<Sample> samples;
  samples.reserve(static_cast<std::size_t>(o.cfg.seconds * 1e9 / static_cast<double>(o.cfg.period_ns)) + 1024);

  // 1) 로깅(소비자) 스레드 시작 — 일반 우선순위
  std::thread logger(logger_thread_main, &running, &samples);

  // 2) 이 스레드(main)가 RT 스레드가 되어 루프를 돈다
  RtLoop loop(o.cfg);
  std::uint64_t iterations = loop.run(g_ring, drops);

  // 3) 끝났다고 알리고 로깅 스레드가 남은 것을 비울 때까지 기다린다
  running.store(false, std::memory_order_release);
  logger.join();

  // 4) 통계 계산. period error 는 첫 샘플(iter 0, 값 0)을 뺀다.
  std::vector<std::int64_t> wake_values, period_values, work_values;
  for (std::size_t i = 0; i < samples.size(); ++i) {
    wake_values.push_back(samples[i].wake_lat_ns);
    work_values.push_back(samples[i].work_ns);
    if (samples[i].iter > 0) {
      period_values.push_back(samples[i].period_err_ns);
    }
  }
  Stats wake = compute_stats(wake_values);
  Stats period_err = compute_stats(period_values);
  Stats work = compute_stats(work_values);

  // 5) 출력
  std::uint64_t drop_count = drops.load();
  print_report(o, loop.status(), iterations, samples.size(), drop_count, wake, period_err, work);
  if (!o.json_path.empty()) {
    write_json(o, loop.status(), iterations, samples.size(), drop_count, wake, period_err, work);
  }
  if (!o.csv_path.empty()) {
    write_csv(o, samples);
  }

  // 종료 코드: 드롭이 있으면 1. CI 에서 "로깅이 RT 루프를 못 따라갔다"를 실패로 잡기 위해.
  if (drop_count == 0) {
    return 0;
  }
  return 1;
}
