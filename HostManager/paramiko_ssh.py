#coding=utf-8
#!/usr/bin/env python

# -*- encoding: utf-8 -*-

__author__ = 'yuanwm <ywmpsn@163.com>'

import paramiko
import os
import select
import sys
import tty
import termios
from stat import S_ISDIR
from multiprocessing import Pool
import os, time
#需要使用进程Queue
import multiprocessing
import pickle


class SSHConnection( object ):
    """定义一个类SSH客户端对象
    """

    def __init__(self, hostip, port, user_name, pass_word):
        """
        初始化各类属性
        """
        self._HostIp = hostip
        self._Port = port
        self._UserName = user_name
        self._PassWord = pass_word
        self._Trans = None
        self._XShellChan = None
        self._SSH = None
        self._Sftp = None
        self._Que = None    #消费者队列
        self._ProQue = None    #生产队列
        self._Pool = None
        self._Event = None

    def connect(self):
        """
        与指定主机建立Socket连接
        """
        # 建立socket
        self._Trans = paramiko.Transport((self._HostIp, int(self._Port)))

        # 启动客户端
        self._Trans.start_client()
        # 如果使用rsa密钥登录的话--这里一般不用直接注释了
        '''
        key_file = '~.ssh/id_rsa'
        pri_key = paramiko.RSAKey.from_private_key_file(default_key_file)
        self._Trans.auth_publickey(username = self._UserName, key=prikey)
        '''
        # 使用用户名和密码登录
        self._Trans.auth_password(username = self._UserName, password = self._PassWord)

        # 封装transport
        self._SSH = paramiko.SSHClient()
        self._SSH._transport = self._Trans
        # 自动添加策略，保存服务器的主机名和密钥信息
        self._SSH.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def remote_producer(self, remote_dir, local_dir):
        """远程Sftp数据生产者
        遍历远程目录，将生成的数据put到本地消费者队列
        """
        self.connect()
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        print('我是生产者,Run task %s PID(%s).PPID(%s)..' % (remote_dir, os.getpid(), os.getppid()))
        start = time.time()
        #获取目录信息，将获取到的
        self.get_remote_dir_all_files(remote_dir, remote_dir, local_dir)
        end = time.time()
        print('Task %s runs %0.2f seconds.' % (remote_dir, (end - start)))

    def local_consumer(self, ori_remote_dir, local_dir):
        """本地Sftp数据消费者
        接收远程回传的队列中数据，回传本地数据
        """
        # print(file)
        # (file_path, qq)=file)
        self.connect()
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        #当队列不为空的时候进行文件下载
        print('我是消费者,Run task PID(%s).PPID(%s)..' % (os.getpid(), os.getppid()))
        while not self._Event.is_set():
            try:
                file_dir=self._Que.get(timeout=2)   #两秒超时，捕获异常去检测事件状态
                print('队列目前的情况:',self._Que.qsize())
                #(file_path,file_name)=os.path.split(file_dir)
                print('消费者Run task %s (%s)...' % (file_dir, os.getpid()))
                start = time.time()
                local_file=local_dir+os.path.sep+file_dir[len(ori_remote_dir):len(file_dir)]
                print('下载数据[%s][%s]' % (file_dir,local_file))
                #self.sftp_get(ori_remote_dir, file_dir, local_file)
                end = time.time()
            except self._Que.Empty:
                continue    #取检测事件
            finally:    #最后要将task_done将信息穿个jion判断是否消费完毕
                print('Task %s runs %0.2f seconds.' % (file_dir, (end - start)))
            self._Que.task_done()
        print('我已经收到了退出事件[%d]', os.getpid())
    def get_remote_dir_all_files(self, ori_remote_dir, new_remote_dir, local_dir):
        """
        获取远端linux主机上指定目录及其子目录下的所有文件
        """
        # 只获取文件夹
        if new_remote_dir[-1] == '/':
            new_remote_dir = new_remote_dir[0:-1]

        #获取远程文件列表
        print('访问文件列表:', new_remote_dir)
        files = self._Sftp.listdir_attr(new_remote_dir)
        for file in files:
            # 去掉路径字符串最后的字符'/'，如果有的话
            if new_remote_dir[-1] == '/':
                new_remote_dir = new_remote_dir[0:-1]
            filename = new_remote_dir + '/' + file.filename
            if S_ISDIR(file.st_mode):
                #在本地建立文件夹
                local_dir_new=local_dir+os.path.sep+filename[len(ori_remote_dir)+1:len(filename)]
                print('本地建立:', local_dir_new)
                #os.makedirs(local_dir_new, exist_ok=True)
                #进一步递归遍历
                self.get_remote_dir_all_files(ori_remote_dir, filename, local_dir)
            else:
                print('文件[%s]加入队列!' % filename)
                self._Que.put(filename)
        return True
    @staticmethod
    def sftp_mul_thread_get_dir(HostIp, HostPort, HostName, HostPassword,remote_path, local_path, thread_num=0):
        """
        多线程实现SFTP功能下载文件夹功能，可以使用相对路径，但必须是文件
        """
        if len(remote_path) == 0 or len(local_path) == 0:
            print("路径存在空的情况![%s][%s]" % (remote_path, local_path))
            return False

        #原始远程文件夹
        if remote_path[-1] == '/':
            remote_path = remote_path[0:-1]

        #原始远程文件夹
        if local_path[-1] == os.path.sep:
            local_path = local_path[0:-1]
        qq=multiprocessing.Manager()
        _Que=qq.Queue()

        # 获取远端linux主机上指定目录及其子目录下的所有文件
        _Que.put(remote_path)
        ps = []
        ssh = SSHConnection(HostIp, HostPort, HostName, HostPassword)
        ssh._Que = _Que

        #定义事件
        ssh._Event=multiprocessing.Event()
        ssh._Event.clear()

        print('启动生产者')
        pp = multiprocessing.Process(target=ssh.remote_producer, args=(remote_path,local_path))

        print('启动生产者1')
        pp.start()

        print('启动消费者...')
        for i in range(5):
            # 创建子进程实例
            ssh._Que=_Que
            p = multiprocessing.Process(target=ssh.local_consumer, args=(remote_path,local_path))
            ps.append(p)
        # 开启进程
        for i in range(5):
            ps[i].start()

        #等待生产者退出
        pp.join()
        print("生产者退出")

        #等待队列退出
        ssh._Que.join()
        print("队列退出")

        #通知消费者退出
        ssh._Event.set()

        # 等待消费者退出
        for i in range(5):
            ps[i].join()

        print("主进程终止")

    def sftp_get(self, remote_path, local_path):
        """
        实现SFTP功能下载文件功能，可以使用相对路径，但必须是文件
        """
        if len(remote_path) == 0 or len(local_path) == 0:
            print ("路径存在空的情况![%s][%s]" % (remote_path, local_path))
            return False
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        try:
            self._Sftp.get(remote_path, local_path)
        except Exception as err_msg:
            print('获取文件失败![%s]' % err_msg)

    def sftp_put(self, local_path, remote_path):
        """
        实现SFTP上传文件功能，可以使用相对路径，但必须是文件
        """
        if len(remote_path) == 0 or len(local_path) == 0:
            print ("路径存在空的情况![%s][%s]" % (remote_path, local_path))
            return False
        if self._Sftp is None:
            # 获取SFTP实例
            self._Sftp = paramiko.SFTPClient.from_transport(self._Trans)
        try:
            self._Sftp.put(local_path, remote_path)
        except Exception as err_msg:
            print('上传文件失败![%s]' % err_msg)


    def shell_cmd(self, cmd):
        """
        在主机上执行单个shell命令
        """
        if len(cmd) == 0:
            os.system('echo "命令为空，请重新输入!" >&2 ')

        stdin, stdout, stderr = self._SSH.exec_command(cmd)
        chan=stdout.channel
        # 返回状态
        status=chan.recv_exit_status()

        #分别返回标准错误，标准输出
        out=stdout.read()
        if len(out) > 0:
            out.strip()
            os.system('echo "%s" >&1' % out.decode().encode('UTF-8'))
        err=stderr.read()
        if len(err)>0:
            err.strip()
            os.system('echo "%s" >&2' % err)
        # 返回shell命令的状态
        return status


    def x_shell(self):
        """
        实现一个XShell，登录到系统就不断输入命令同时返回结果,支持自动补全，直接调用服务器终端
        """
        # 打开一个通道
        if self._XShellChan is None:
            self._XShellChan = self._Trans.open_session()
            # 获取终端
            self._XShellChan.get_pty()
            # 激活终端，这样就可以登录到终端了，就和我们用类似于XShell登录系统一样
            self._XShellChan.invoke_shell()
            # 获取原操作终端属性
        old_tty_arg = termios.tcgetattr(sys.stdin)
        try:
            # 将现在的操作终端属性设置为服务器上的原生终端属性,可以支持tab了
            tty.setraw(sys.stdin)
            self._XShellChan.settimeout(0)
            while True:
                read_list, write_list, err_list = select.select([self._XShellChan, sys.stdin, ], [], [])
                # 如果是用户输入命令了,sys.stdin发生变化
                if sys.stdin in read_list:
                    # 获取输入的内容，输入一个字符发送1个字符
                    input_cmd = sys.stdin.read(1)
                    # 将命令发送给服务器
                    self._XShellChan.sendall(input_cmd)

                # 服务器返回了结果,self._XShellChan通道接受到结果,发生变化 select感知到
                if self._XShellChan in read_list:
                    # 获取结果
                    result = self._XShellChan.recv(65535)
                    # 断开连接后退出
                    if len(result) == 0:
                        print("\n**连接已断开**\n")
                        break
                    # 输出到屏幕
                    sys.stdout.write(result.decode())
                    sys.stdout.flush()
        finally:
            # 执行完后将现在的终端属性恢复为原操作终端属性
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty_arg)
            # 关闭通道
            self._XShellChan.close()


    def disconnect(self):
        """
        主机任务结束后执行
        """
        # 关闭链接
        if self._Trans is not None:
            self._Trans.close()
        if self._XShellChan is not None:
            self._XShellChan.close()
        if self._Sftp is not None:
            self._Sftp.close()

    def __getstate__(self):
        self_dict = self.__dict__.copy()
        del self_dict['pool']
        return self_dict

    def __setstate__(self, state):
        self.__dict__.update(state)
