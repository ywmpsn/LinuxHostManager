#coding=utf-8
#!/usr/bin/env python

__author__ = 'yuanwm <ywmpsn@163.com>'

from paramiko_ssh import SSHConnection
import sys
import os

'''
在这里定义IP与用户名以及密码，暂时使用字典定义（防止无第三方的模块解析配置文件）
'''
HostMsg = {
    "103.46.128.49":{
        "account":{
            "HostPassWord": "ie5Pxi$t",
            "HostPort": "19776"
        }
    },
    "192.168.1.7": {
        "account": {
            "HostPassWord": "ie5Pxi$t",
            "HostPort": "22"
        }
    },
    "10.113.178.111": {
        "Note":"预演环境1号机",
        "account": {
            "HostPassWord": "iC4me#ck",
            "HostPort": "22"
        }
    }
}

if __name__ == "__main__":

    #执行一个终端
    if len(sys.argv) < 4:
        os.system('''echo "参数错误!,例如：
        %s -xshell 192.168.1.1 account (执行一个xshell终端)
        %s -sh 192.168.1.1 account 'df -h' (执行df -h这个命令并返回)"
        %s -put 192.168.1.1 account 本地文件 远程文件(执行一个xshell终端)
        %s -get 192.168.1.1 account 远程文件 本地文件 (执行df -h这个命令并返回)"'''
        % (sys.argv[0],sys.argv[0],sys.argv[0],sys.argv[0]))
        exit(1)
    OperaType=sys.argv[1]
    HostIp = sys.argv[2]
    HostName = sys.argv[3]
    HostPassword = None
    HostPort = None

    # 获取密码
    try:
        HostPassword = HostMsg[HostIp][HostName]['HostPassWord']
        HostPort = HostMsg[HostIp][HostName]['HostPort']
    except Exception as ErrMsg:
        print('获取主机信息错误![%s]' % ErrMsg)
        exit(0)

    #ssh = SSHConnection(HostIp, HostPort, HostName, HostPassword)
    #ssh.connect()
    #ssh.sftp_mul_thread_get_dir(ssh, sys.argv[4], sys.argv[5])
    ssh = SSHConnection(HostIp, HostPort, HostName, HostPassword)
    SSHConnection.sftp_mul_thread_get_dir(HostIp, HostPort, HostName, HostPassword,sys.argv[4], sys.argv[5])
    exit(0)
    ssh = SSHConnection(HostIp, HostPort, HostName, HostPassword)
    try:
        ssh.connect()
        if OperaType == '-xshell':
            ssh.x_shell()
        elif OperaType == '-sh':
            command = sys.argv[4]
            ssh.shell_cmd(command)
        elif OperaType == '-put':
            ssh.sftp_put(sys.argv[4], sys.argv[5])
        elif OperaType == '-get':
            ssh.sftp_get(sys.argv[4], sys.argv[5])
        elif OperaType == '-getdir':
            SSHConnection.sftp_mul_thread_get_dir(sys.argv[4], sys.argv[5])
        else:
            print("不支持操作类型[%s]" % OperaType)
    except Exception as ErrMsg:
        print('执行错误![%s]' % ErrMsg)
        exit(0)

    finally:
        ssh.disconnect()
