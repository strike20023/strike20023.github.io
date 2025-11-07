import socket
import threading
import argparse
import select
import struct


def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("socket closed during recv_exact")
        data += chunk
    return data


def handle_client(conn):
    try:
        conn.settimeout(10)
        # 方法协商：VER, NMETHODS, METHODS[...]
        head = recv_exact(conn, 2)
        ver, nmethods = head[0], head[1]
        if ver != 5:
            raise ValueError("Unsupported SOCKS version")
        methods = recv_exact(conn, nmethods)
        # 只支持 0x00（NO AUTH）
        if 0x00 in methods:
            conn.sendall(b"\x05\x00")
        else:
            conn.sendall(b"\x05\xFF")
            return

        # 请求：VER, CMD, RSV, ATYP, DST.ADDR, DST.PORT
        req_head = recv_exact(conn, 4)
        ver, cmd, rsv, atyp = req_head
        if ver != 5 or rsv != 0:
            raise ValueError("Invalid request header")

        # 地址解析
        dst_addr = None
        family = socket.AF_INET
        if atyp == 0x01:  # IPv4
            dst_addr = socket.inet_ntoa(recv_exact(conn, 4))
            family = socket.AF_INET
        elif atyp == 0x03:  # domain
            l = recv_exact(conn, 1)[0]
            dst_addr = recv_exact(conn, l).decode("utf-8", errors="ignore")
            # 先尝试 IPv4，再尝试 IPv6
            family = None  # 决定在连接时
        elif atyp == 0x04:  # IPv6
            dst_addr = socket.inet_ntop(socket.AF_INET6, recv_exact(conn, 16))
            family = socket.AF_INET6
        else:
            # 地址类型不支持
            conn.sendall(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
            return

        dst_port = struct.unpack("!H", recv_exact(conn, 2))[0]

        if cmd != 0x01:  # 仅支持 CONNECT
            conn.sendall(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
            return

        # 建立到目标的连接
        remote = None
        try:
            if atyp == 0x03:  # 域名解析
                # 优先 IPv4
                infos = socket.getaddrinfo(dst_addr, dst_port, 0, socket.SOCK_STREAM)
                err = None
                for family_i, socktype, proto, cname, sockaddr in infos:
                    try:
                        remote = socket.socket(family_i, socket.SOCK_STREAM)
                        remote.settimeout(10)
                        remote.connect(sockaddr)
                        family = family_i
                        break
                    except Exception as e:
                        err = e
                        if remote:
                            remote.close()
                            remote = None
                if remote is None:
                    raise err or OSError("getaddrinfo/connect failed")
            else:
                remote = socket.socket(family, socket.SOCK_STREAM)
                remote.settimeout(10)
                if family == socket.AF_INET:
                    remote.connect((dst_addr, dst_port))
                else:
                    remote.connect((dst_addr, dst_port, 0, 0))

            # 成功应答（BND 使用本地绑定地址）
            baddr, bport = None, None
            if family == socket.AF_INET:
                baddr, bport = remote.getsockname()
                rep = b"\x05\x00\x00\x01" + socket.inet_aton(baddr) + struct.pack("!H", bport)
            else:
                sn = remote.getsockname()
                baddr, bport = sn[0], sn[1]
                rep = b"\x05\x00\x00\x04" + socket.inet_pton(socket.AF_INET6, baddr) + struct.pack("!H", bport)
            conn.sendall(rep)

            # 开始转发
            conn.settimeout(None)
            remote.settimeout(None)
            while True:
                r, _, _ = select.select([conn, remote], [], [])
                if conn in r:
                    data = conn.recv(4096)
                    if not data:
                        break
                    remote.sendall(data)
                if remote in r:
                    data = remote.recv(4096)
                    if not data:
                        break
                    conn.sendall(data)
        except Exception:
            # 一般失败
            try:
                conn.sendall(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
            except Exception:
                pass
        finally:
            try:
                if remote:
                    remote.close()
            except Exception:
                pass
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_server(host="0.0.0.0", port=1080, backlog=128):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(backlog)
    print(f"SOCKS5 server listening on {host}:{port}")
    try:
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(conn,), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\nSOCKS5 server shutting down...")
    finally:
        s.close()


def main():
    parser = argparse.ArgumentParser(description="Simple socket-based SOCKS5 server (NO AUTH, CONNECT only)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8809)
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()