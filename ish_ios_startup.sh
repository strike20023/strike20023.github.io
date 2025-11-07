#!/bin/sh
set -e

# 进度条与步骤说明
bar_width=5
total_steps=19
current_step=0
current_desc=""

trap 'status=$?; if [ "$status" -ne 0 ]; then printf "\n发生错误（第 %d/%d 步）：%s\n" "$current_step" "$total_steps" "$current_desc"; fi' EXIT

update_progress() {
  percent=$(( current_step * 100 / total_steps ))
  filled=$(( percent * bar_width / 100 ))

  bar=""
  i=0
  while [ $i -lt $filled ]; do
    bar="${bar}#"
    i=$(( i + 1 ))
  done
  while [ $i -lt $bar_width ]; do
    bar="${bar}-"
    i=$(( i + 1 ))
  done

  printf "\r[%-${bar_width}s] %3d%%  第 %d/%d 步：%s" "$bar" "$percent" "$current_step" "$total_steps" "$current_desc"
}

printf "开始安装与配置 (iSH iOS / Alpine + OpenRC + SSH)...\n"

# 1) 安装基础包
current_desc="安装apk包"
apk add openssh curl openrc python3 nano zsh
current_step=$((current_step + 1))
update_progress

# 2) 创建 SSH 目录
current_desc="创建 SSH 授权文件目录"
mkdir -p ~/.ssh
current_step=$((current_step + 1))
update_progress

# 3) 下载并设置授权公钥
current_desc="下载并设置授权公钥"
curl -sL http://strike20023.github.io/public.key >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
current_step=$((current_step + 1))
update_progress

# 4) 修改 SSH 端口
current_desc="修改 SSH 端口为 22022"
sed -i 's/^#Port 22/Port 22022/' /etc/ssh/sshd_config
current_step=$((current_step + 1))
update_progress

# 5) 初始化 OpenRC
current_desc="初始化 OpenRC 默认运行级别"
openrc default
current_step=$((current_step + 1))
update_progress

# 6) 将 sshd 加入开机启动
current_desc="将 sshd 加入开机启动"
rc-update add sshd
current_step=$((current_step + 1))
update_progress

# 7) 启动 sshd 服务
current_desc="启动 sshd 服务"
if ! rc-service sshd status; then
    rc-service sshd start
fi
current_step=$((current_step + 1))
update_progress

# 8) 创建保持后台运行的服务脚本
current_desc="创建 runbg 后台服务脚本"
cat > /etc/init.d/runbg <<'INIT'
#!/sbin/openrc-run
#
# This service reads the GPS and discards the output to /dev/null.
# This is not tracking you in any way. The sole purpose of this
# is to ensure an iOS program continues to run in the background.
# This process has no noticeable impact on battery life.
#

description="Reads GPS to ensure iSH continues to run in the background"

command="/bin/cat"
command_args="/dev/location > /dev/null"
command_background="YES"

pidfile="/run/runbg.pid"
INIT
current_step=$((current_step + 1))
update_progress

# 9) 赋予服务脚本执行权限
current_desc="赋予服务脚本执行权限"
chmod 755 /etc/init.d/runbg
current_step=$((current_step + 1))
update_progress

# 10) 将 runbg 加入默认运行级别
current_desc="将 runbg 加入默认运行级别"
rc-update add runbg default
current_step=$((current_step + 1))
update_progress

# 11) 启动 runbg 服务
current_desc="启动 runbg 服务"
if ! rc-service runbg status; then
    rc-service runbg start
fi
current_step=$((current_step + 1))
update_progress

# 12) 下载socks5代理脚本并且部署
current_desc="下载socks5代理脚本并且部署"
curl -sL https://strike20023.github.io/socks5_server.py > /usr/local/bin/socks5.sh && chmod 755 /usr/local/bin/socks5.sh
current_step=$((current_step + 1))
update_progress

# 13）创建 socks5 后台服务脚本"

current_desc="创建 socks5 后台服务脚本"
cat > /etc/init.d/socks5 <<'INIT'
#!/sbin/openrc-run
#
# This service starts a socks5 proxy server on port 8809.
#

description="Starts a socks5 proxy server on port 8809"

command="/usr/bin/python3"
command_args="/usr/local/bin/socks5.sh"
command_background="YES"

pidfile="/run/socks5.pid"
INIT
current_step=$((current_step + 1))
update_progress

# 14) 赋予服务脚本执行权限
current_desc="赋予服务脚本执行权限"
chmod 755 /etc/init.d/socks5
current_step=$((current_step + 1))
update_progress

# 15）将 socks5 加入默认运行级别
current_desc="将 socks5 加入默认运行级别"
rc-update add socks5 default
current_step=$((current_step + 1))
update_progress

# 16）启动 socks5 服务
current_desc="启动 socks5 服务"
if ! rc-service socks5 status; then
    rc-service socks5 start
fi
current_step=$((current_step + 1))
update_progress

# 17) 修改 zsh 为默认 shell
current_desc="修改 zsh 为默认 shell"
chsh -s /bin/zsh
current_step=$((current_step + 1))
update_progress

# 18) 安装oh-my-zsh
current_desc="安装oh-my-zsh"
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
current_step=$((current_step + 1))
update_progress

# 19) 限制oh-my-zsh的更新

current_desc="限制oh-my-zsh的更新"
echo "DISABLE_AUTO_UPDATE=true" >> ~/.zshrc
current_step=$((current_step + 1))
update_progress

zsh
printf "\n全部步骤完成！现在可通过端口 22022 进行 SSH 登录。socks5 代理端口为 8809\n"
## wget -qO- https://strike20023.github.io/ish_ios_startup.sh | sh