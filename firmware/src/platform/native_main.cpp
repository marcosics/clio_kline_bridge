// Plataforma PC: el MISMO núcleo del firmware con una línea K virtual (eco, tiempos, fast init y 5 baudios)
// y centralitas simuladas. Habla por TCP como el ESP, así la web y las pruebas usan el firmware real sin placa.
//   pio run -e native && .pio/build/native/program --port 2323 [--noecho] [--deaf] [--stuck-low] [--settings f]
#ifdef NATIVE
#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <signal.h>
#include <sys/socket.h>
#include <unistd.h>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <deque>
#include <string>
#include <thread>
#include <vector>
#include "../core/cmd.h"
#include "../core/ecusim.h"
#include "../core/util.h"

using Clock = std::chrono::steady_clock;
static const Clock::time_point T0 = Clock::now();
static uint32_t nowMs() { return (uint32_t)std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - T0).count(); }
static uint32_t nowUs() { return (uint32_t)std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - T0).count(); }

// ---------------------------------------------------------------- línea K virtual
struct Bus {
  bool echo = true, deaf = false, stuckLow = false;
  bool gpio = false, txHigh = true;
  uint32_t lowStart = 0, lastTraffic = 0, awakeUntil = 0;
  std::vector<std::pair<uint32_t, bool>> edges;   // flancos del TX en modo GPIO (init a 5 baudios)
  std::deque<std::pair<uint32_t, uint8_t>> rx;    // bytes que verá el tester: (instante, byte)
  std::vector<uint8_t> frame;
  uint32_t frameMs = 0;
  int slowState = 0;                               // 1: esperando ~KB2 del tester
  uint8_t slowAddr = 0;

  void schedule(uint32_t at, const uint8_t* b, int n) {
    for (int i = 0; i < n; i++) rx.push_back({at + i, b[i]});   // ~1 ms por byte a 10400 baudios
  }
  void tx(bool high) {
    uint32_t t = nowMs();
    if (!high && txHigh) lowStart = t;
    if (high && !txHigh) {
      uint32_t d = t - lowStart;
      if (d >= 20 && d <= 30 && !deaf) awakeUntil = t + 5000;   // fast init: TiniL 25 ms
    }
    if (high != txHigh) edges.push_back({t, high});
    txHigh = high;
  }
  void toGpio() { gpio = true; edges.clear(); }
  void toUart() {
    gpio = false;
    // ¿era un init a 5 baudios? start bajo de 200 ms y 8 bits de 200 ms
    if (edges.size() >= 2 && !edges[0].second) {
      uint32_t t0 = edges[0].first;
      auto level = [&](uint32_t t) {
        bool l = true;
        for (auto& e : edges) if (e.first <= t) l = e.second;
        return l;
      };
      if (nowMs() - t0 >= 1700) {
        uint8_t a = 0;
        for (int b = 0; b < 8; b++) a |= (uint8_t)(level(t0 + 300 + b * 200) ? 1 : 0) << b;
        if (ecuSimPresent(a) && !deaf) {
          const uint8_t kb[3] = {0x55, 0x08, 0x08};
          schedule(nowMs() + 200 + 60, kb, 1);
          schedule(nowMs() + 200 + 70, kb + 1, 2);
          slowState = 1;
          slowAddr = a;
        }
      }
    }
    edges.clear();
  }
  int rxLevel() { return stuckLow ? 0 : (txHigh ? 1 : 0); }
  void write(const uint8_t* b, size_t n) {
    uint32_t t = nowMs();
    if (echo) schedule(t, b, (int)n);
    for (size_t i = 0; i < n; i++) ecuByte(b[i], t);
  }
  int read() {
    if (!rx.empty() && rx.front().first <= nowMs()) {
      uint8_t c = rx.front().second;
      rx.pop_front();
      return c;
    }
    return -1;
  }
  void ecuByte(uint8_t c, uint32_t t) {
    if (slowState == 1) {
      if (c == (uint8_t)~0x08) {
        uint8_t inv = (uint8_t)~slowAddr;
        schedule(t + 30, &inv, 1);
        awakeUntil = t + 5000;
      }
      slowState = 0;
      return;
    }
    if (!frame.empty() && t - frameMs > 20) frame.clear();
    frameMs = t;
    if (frame.empty() && c == 0) return;
    frame.push_back(c);
    int need = kwpFrameLen(frame.data(), (int)frame.size());
    if (need < 0 || (int)frame.size() < need) return;
    std::vector<uint8_t> f = frame;
    frame.clear();
    if (!kwpChecksumOk(f.data(), (int)f.size()) || !(f[0] & 0x80)) return;
    uint8_t dst = f[1], src = f[2];
    if (deaf || !ecuSimPresent(dst) || (int32_t)(awakeUntil - t) < 0) return;   // sin wake-up no contesta
    awakeUntil = t + 5000;                                                         // P3max
    uint8_t a[KBUF], out[KBUF];
    int al = ecuSimAnswer(dst, f.data() + kwpDataOff(f.data()), kwpDataLen(f.data()), a, t);
    if (!al) return;
    int ol = kwpBuild(src, dst, a, al, out);
    schedule(t + (uint32_t)f.size() + 30, out, ol);   // tras nuestro eco + P2 30 ms
  }
};

// ---------------------------------------------------------------- HAL del PC
class NativeHal : public Hal {
 public:
  Bus bus;
  std::string settingsFile;
  std::vector<uint8_t> mem;
  int client = -1;

  uint32_t ms() override { return nowMs(); }
  uint32_t us() override { return nowUs(); }
  void delayMs(uint32_t d) override { std::this_thread::sleep_for(std::chrono::milliseconds(d)); }
  void idle() override { std::this_thread::sleep_for(std::chrono::microseconds(200)); }
  void kUart(uint32_t) override { bus.toUart(); }
  void kGpio() override { bus.toGpio(); }
  void kTx(bool h) override { bus.tx(h); }
  int kRxLevel() override { return bus.rxLevel(); }
  void kWrite(const uint8_t* b, size_t n) override { bus.write(b, n); }
  int kRead() override { return bus.read(); }
  void kTxGate(bool) override {}
  void out(const char* line) override {
    printf("%s\n", line);
    fflush(stdout);
    if (client >= 0) {
      std::string l = std::string(line) + "\r\n";
      if (send(client, l.data(), l.size(), MSG_NOSIGNAL) < 0) { close(client); client = -1; }
    }
  }
  const char* board() override { return "native"; }
  bool loadBlob(void* p, size_t n) override {
    if (settingsFile.empty()) {
      if (mem.size() != n) return false;
      memcpy(p, mem.data(), n);
      return true;
    }
    FILE* f = fopen(settingsFile.c_str(), "rb");
    if (!f) return false;
    bool ok = fread(p, 1, n, f) == n;
    fclose(f);
    return ok;
  }
  bool saveBlob(const void* p, size_t n) override {
    if (settingsFile.empty()) {
      mem.assign((const uint8_t*)p, (const uint8_t*)p + n);
      return true;
    }
    FILE* f = fopen(settingsFile.c_str(), "wb");
    if (!f) return false;
    bool ok = fwrite(p, 1, n, f) == n;
    fclose(f);
    return ok;
  }
  void netInfo(char* b, size_t n) override { snprintf(b, n, "net=tcp-local client=%d", client >= 0); }
  void reboot() override { exit(0); }
};

Hal* gPlatform = nullptr;

int main(int argc, char** argv) {
  signal(SIGPIPE, SIG_IGN);
  static NativeHal hal;
  int port = 2323;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--port" && i + 1 < argc) port = atoi(argv[++i]);
    else if (a == "--noecho") hal.bus.echo = false;
    else if (a == "--deaf") hal.bus.deaf = true;
    else if (a == "--stuck-low") hal.bus.stuckLow = true;
    else if (a == "--settings" && i + 1 < argc) hal.settingsFile = argv[++i];
  }
  gPlatform = &hal;
  outInit(&hal);
  static Settings cfg;
  settingsLoad(cfg);
  gLogLevel = cfg.logLevel;
  static Kwp kwp(hal, cfg);
  static Commands cmds(hal, kwp, cfg);
  kwp.begin();

  int srv = socket(AF_INET, SOCK_STREAM, 0);
  int one = 1;
  setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
  sockaddr_in sa{};
  sa.sin_family = AF_INET;
  sa.sin_port = htons((uint16_t)port);
  sa.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  if (bind(srv, (sockaddr*)&sa, sizeof sa) || listen(srv, 2)) {
    perror("bind");
    return 1;
  }
  fcntl(srv, F_SETFL, O_NONBLOCK);
  emit("DBG", "puente clio-kline native en 127.0.0.1:%d (linea K virtual%s%s)", port, hal.bus.echo ? "" : ", sin eco",
       hal.bus.deaf ? ", UCE sorda" : "");
  std::string buf;
  for (;;) {
    int c = accept(srv, nullptr, nullptr);
    if (c >= 0) {
      if (hal.client >= 0) {
        emit("EVT", "otro cliente se ha conectado: este se cierra");
        close(hal.client);
      }
      setsockopt(c, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
      fcntl(c, F_SETFL, O_NONBLOCK);
      hal.client = c;
      buf.clear();
      cmds.banner();
    }
    if (hal.client >= 0) {
      char tmp[512];
      ssize_t n = recv(hal.client, tmp, sizeof tmp, 0);
      if (n == 0) { close(hal.client); hal.client = -1; }
      for (ssize_t i = 0; i < n; i++) {
        if (tmp[i] == '\n') {
          std::vector<char> l(buf.begin(), buf.end());
          l.push_back(0);
          cmds.handle(l.data());
          buf.clear();
        } else if (tmp[i] != '\r' && buf.size() < LINE_MAX) buf += tmp[i];
      }
    }
    kwp.poll();
    std::this_thread::sleep_for(std::chrono::microseconds(500));
  }
}
#endif
