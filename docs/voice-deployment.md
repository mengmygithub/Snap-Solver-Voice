# 语音增强版部署说明

## 版本与来源

Snap-Solver Voice 基于 Zippland/Snap-Solver 1.5.1 开发，保留原项目历史及 Apache-2.0 许可证。
此版本包含录音转写、校对后发送 AI，以及现有 OpenAI Responses API 适配。
使用本仓库的代码或 Release，不要下载原作者的旧版安装包。

## 环境要求

- 推荐 Python 3.11，最低 Python 3.10。Python 3.9 已停止支持。
- macOS、Windows 或有图形桌面的 Linux；Chrome、Edge 或 Safari，允许麦克风权限。
- 安装依赖、加载页面 CDN 资源和调用 API 均需联网，这不是离线语音识别软件。
- OpenAI API Key、API 余额及 `whisper-1` 调用权限。ChatGPT 订阅不包含 API 额度。
- Linux 截图依赖桌面会话、Tk、scrot，剪贴板依赖 xclip/xsel。
  Ubuntu/Debian 可安装 `python3-venv python3-tk scrot xclip`。
  PyAutoGUI 依赖桌面环境，因此不提供普通无桌面 Docker 镜像。

## 下载与启动

私有仓库需要用有访问权限的 GitHub 账号登录。
可从 GitHub Release 下载 `Snap-Solver-Voice-v1.5.2.zip` 并解压，
也可安装 Git 后运行：

```bash
git clone https://github.com/mengmygithub/Snap-Solver-Voice.git
cd Snap-Solver-Voice
```

macOS / Linux：

```bash
python3 run.py
```

Windows PowerShell：

```powershell
py -3.11 run.py
```

启动器自动创建本机 `.venv`，安装 `requirements.txt` 并启动服务。
打开 http://localhost:5001。终端保持运行，按 Ctrl+C 停止。
首次安装失败时，检查网络后重新执行；启动器不会把失败的安装标为成功。

可选参数：

```bash
python3 run.py --install-only
python3 run.py --reinstall
python3 run.py --port 5002
```

`--install-only` 仅安装；`--reinstall` 重新安装当前依赖；端口被占用时明确报错，不会悄悄更换。
不要从旧机器复制 `.venv`。如果已有 Python 3.9 创建的 `.venv`，先将其改名备份，
再用 Python 3.11 运行启动器。

## 配置与语音流程

1. 打开「设置」，填写 OpenAI API Key，并选取账号可用的 AI 模型。
2. 点击相机旁的麦克风，允许浏览器录音；macOS 还需要系统麦克风权限。
3. 再次点击麦克风停止录音，页面立即显示转写中的状态。
4. 转写完成后，在首页「语音转文字」文本框内校对或修改。
5. 点击下方「发送至AI」，校对后的文字才会发送给当前选择的分析模型。

ASR 固定使用 OpenAI `whisper-1`，与设置中选取的分析模型是两个独立请求。
停止录音后音频就会上传用于 ASR；“确认后发送”只针对后续 AI 文本分析。
若启用了 OpenAI 中转地址，音频也会发送到该地址，须确认其可信且支持音频转写接口。
服务不主动将录音保存成项目文件。请使用短录音，上传请求须小于 25 MB。
ASR 请求不自动重试，并有超时提示，避免无限等待。

模型下拉菜单只是本地配置，不是账号权限清单；部分继承的模型 ID 可能不适用于你的服务。
`sk-` 前缀不能证明服务来源或调用权限。出现 `model not found` 时应根据
OpenAI 官方 API 或所用服务商的可用模型清单核对 `config/models.json` 中的 ID。
本版本未使用个人密钥验证菜单中的所有模型，不承诺全部可调用。

## 密钥与数据

- 新电脑需重新在设置页填写 Key；也支持环境变量 `OPENAI_API_KEY` 作为 OpenAI 密钥后备。
- `config/api_keys.json`、`config/api_base_urls.json`、`.env`、`.venv` 不提交或打包。
- API Key 保存在本机配置文件中，不是加密保险库。只在自己信任的电脑上使用。
- 不要把聊天内容、私人录音或含密钥的截图提交到 GitHub。
- 中转地址和提示词属于配置文件，发布改动前检查其中没有私有信息。
- 打包源码不会迁移浏览器本地设置，另一台电脑需要重新选择模型、代理及提示词。

## 本机与局域网

默认绑定 `127.0.0.1:5001`。录音在浏览器所在设备采集，
截图和剪贴板在运行 Python 的电脑上执行。

仅在可信网络需要共享时显式使用：

```bash
python3 run.py --host 0.0.0.0
```

普通 `http://局域网IP:端口` 通常不能使用麦克风。录音必须用 localhost 或配置可信 HTTPS。
本程序的设置、密钥、剪贴板和截图接口没有用户认证，局域网访问者可操作它们；
不能直接开放公网端口。需要远程使用时应另行配置认证、HTTPS 和访问控制。

## 验证与更新

安装后运行离线回归测试，不会读取个人密钥或发送付费 API 请求：

```bash
.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/voice.test.cjs
```

Windows 将第一条命令的 Python 路径替换为 `.venv\Scripts\python.exe`。
前端测试需要 Node.js 22，仅部署使用无需 Node.js。GitHub Actions 自动执行相同检查。
测试覆盖 ASR 请求、错误、代理隔离、录音停止回调、转写展示和编辑后单次发送；
真实麦克风、账号权限和计费结果需在目标机器验证。

Git 安装可执行 `git pull --ff-only` 更新，再运行 `run.py`；
依赖文件变化时会重新安装。更新前停止服务，备份本机密钥和自定义配置。
ZIP 安装请解压到新目录，重新安装依赖，勿覆盖带个人配置的旧目录。
