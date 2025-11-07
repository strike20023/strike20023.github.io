apk add openssh curl openrc python3
mkdir -p ~/.ssh
curl -sL http://strike20023.github.io/public.key >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
sed -i 's/^#Port 22/Port 22022/' /etc/ssh/sshd_config
openrc default
rc-update add sshd
rc-service sshd start
echo '''#!/sbin/openrc-run
#
# Copyright (c) 2021-2024: Jacob.Lundqvist@gmail.com
# License: MIT
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

pidfile="/run/runbg.pid"''' > /etc/init.d/runbg
chmod 755 /etc/init.d/runbg
rc-update add runbg default
rc-service runbg start
