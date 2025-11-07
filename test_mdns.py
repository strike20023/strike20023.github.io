#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import struct
import time

MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353

# 配置：根据需求修改
INSTANCE_NAME = "Zhe's iPhone"
SERVICE_TYPE = "_ssh._tcp.local."  # 服务类型（带结尾点）
SERVICE_PORT = 8080                 # 服务端口
TXT_RECORDS = ["ssh-server=ish-app", "port=22022", "warning=do not use"]  # 简单 TXT 信息

ANNOUNCE_INTERVAL = 30   # 周期性公告的间隔秒数
INITIAL_BURST = [0.0, 0.2, 1.0]  # RFC 6762 建议的初始快速广播间隔

def encode_name(name: str) -> bytes:
    name = name.strip(".")
    parts = name.split(".") if name else []
    out = bytearray()
    for p in parts:
        b = p.encode("utf-8")
        if len(b) > 63:
            raise ValueError("Label too long in name: %s" % p)
        out.append(len(b))
        out += b
    out.append(0)
    return bytes(out)

def pack_header(id_: int, flags: int, qd: int, an: int, ns: int, ar: int) -> bytes:
    return struct.pack("!HHHHHH", id_, flags, qd, an, ns, ar)

def rr(name: str, rrtype: int, rrclass: int, ttl: int, rdata: bytes) -> bytes:
    return encode_name(name) + struct.pack("!HHIH", rrtype, rrclass, ttl, len(rdata)) + rdata

def rr_ptr(name: str, target: str, ttl: int = 4500) -> bytes:
    return rr(name, 12, 1, ttl, encode_name(target))

def rr_srv(name: str, target: str, port: int, ttl: int = 120) -> bytes:
    rdata = struct.pack("!HHH", 0, 0, port) + encode_name(target)
    return rr(name, 33, 0x8001, ttl, rdata)

def rr_txt(name: str, kvs, ttl: int = 120) -> bytes:
    payload = bytearray()
    for s in kvs:
        b = s.encode("utf-8")
        if len(b) > 255:
            b = b[:255]
        payload.append(len(b))
        payload += b
    return rr(name, 16, 0x8001, ttl, bytes(payload))

def rr_a(name: str, ipv4: str, ttl: int = 120) -> bytes:
    return rr(name, 1, 0x8001, ttl, socket.inet_aton(ipv4))

def get_default_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def build_announcement(hostname: str, host_ip: str):
    instance_fqdn = f"{INSTANCE_NAME}.{SERVICE_TYPE}".strip(".") + "."
    records = [
        rr_ptr("_services._dns-sd._udp.local.", SERVICE_TYPE),
        rr_ptr(SERVICE_TYPE, instance_fqdn),
        rr_srv(instance_fqdn, hostname, SERVICE_PORT),
        rr_txt(instance_fqdn, TXT_RECORDS),
        rr_a(hostname, host_ip),
    ]
    header = pack_header(0, 0x8400, 0, len(records), 0, 0)
    return header + b"".join(records)

def main():
    local_ip = get_default_ip()
    hostname = socket.gethostname().split(".")[0] + ".local."
    print(f"[mdns] Using host: {hostname} ip: {local_ip}")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # 仅发送：明确设置多播接口与 TTL，避免路由错误
    try:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
    except Exception as e:
        print(f"[mdns] set IP_MULTICAST_IF failed: {e}")
    try:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    except Exception as e:
        print(f"[mdns] set IP_MULTICAST_TTL failed: {e}")
    # 某些受限环境需要绑定到本地接口才能发送
    try:
        s.bind((local_ip, 0))
    except Exception:
        pass

    # 初始快速广播
    for delay in INITIAL_BURST:
        time.sleep(delay)
        pkt = build_announcement(hostname, local_ip)
        s.sendto(pkt, (MDNS_GROUP, MDNS_PORT))
        print(f"[mdns] Initial announce sent (delay={delay}s)")

    last_announce = time.monotonic()

    # 周期性广播
    try:
        while True:
            now = time.monotonic()
            if now - last_announce >= ANNOUNCE_INTERVAL:
                pkt = build_announcement(hostname, local_ip)
                s.sendto(pkt, (MDNS_GROUP, MDNS_PORT))
                print("[mdns] Periodic announce sent")
                last_announce = now
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[mdns] Stopped by user")
    finally:
        s.close()

if __name__ == "__main__":
    main()