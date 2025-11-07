apk add build-base
echo '''#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <net/if.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

static int seen(const char *name, char list[][IFNAMSIZ], int count) {
for (int i = 0; i < count; i++) if (strncmp(name, list[i], IFNAMSIZ) == 0) return 1;
return 0;
}

int main(void) {
int s = socket(AF_INET, SOCK_DGRAM, 0);
if (s < 0) {
fprintf(stderr, "socket() failed: errno=%d (%s) — continue with pseudo fd\n", errno, strerror(errno));
s = -1; // iSH 内核会允许 ioctl 在受限环境下工作
}
char buf[16384];
struct ifconf ifc;
memset(&ifc, 0, sizeof(ifc));
ifc.ifc_len = sizeof(buf);
ifc.ifc_buf = buf;

if (ioctl(s, SIOCGIFCONF, &ifc) < 0) {
    fprintf(stderr, "SIOCGIFCONF failed: errno=%d (%s)\n", errno, strerror(errno));
    return 1;
}

int n = ifc.ifc_len / sizeof(struct ifreq);
struct ifreq *ifr = (struct ifreq *) buf;
char names[256][IFNAMSIZ];
int name_cnt = 0;

for (int i = 0; i < n; i++) {
    char ifname[IFNAMSIZ]; memset(ifname, 0, sizeof(ifname));
    strncpy(ifname, ifr[i].ifr_name, IFNAMSIZ-1);
    if (seen(ifname, names, name_cnt)) continue; // 去重
    strncpy(names[name_cnt++], ifname, IFNAMSIZ-1);

    // 直接从 SIOCGIFCONF 返回的 ifr_addr 中拿 IPv4
    char ipv4[INET_ADDRSTRLEN] = "";
    struct sockaddr *sa = (struct sockaddr *) &ifr[i].ifr_addr;
    if (sa->sa_family == AF_INET) {
        struct sockaddr_in *sin = (struct sockaddr_in *) &ifr[i].ifr_addr;
        inet_ntop(AF_INET, &sin->sin_addr, ipv4, sizeof(ipv4));
    }

    if (ipv4[0]) printf("%s ipv4=%s\n", ifname, ipv4);
    else printf("%s\n", ifname);
}
return 0;}''' > ifnames.c

gcc -O2 ifnames.c -o ifnames
./ifnames