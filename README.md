# 反馈机器人

一个基于 Telegram Bot API 的反馈和求片机器人。

## 功能特点

- 支持多种反馈类型（问题反馈、功能建议、疑问咨询等）
- 支持电影资源搜索和订阅
- 管理员功能（查看统计、处理反馈、控制功能开关）
- 自动清理过期数据

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

1. 复制 `config.example.json` 为 `config.json`
2. 编辑 `config.json` 填写必要的配置信息：
   - `bot_token`: Telegram Bot Token
   - `admin_ids`: 管理员用户 ID 列表
   - `feedback_group`: 反馈管理群组 ID
   - `db_file`: 数据库文件路径
   - `moviepoilt_username`: MoviePoilt 用户名
   - `moviepoilt_password`: MoviePoilt 密码

## 本地运行

```bash
python3 bot.py
```

## 服务器部署

### 1. 上传文件

将以下文件上传到服务器：

- `bot.py`
- `feedback.py`
- `movie_request.py`
- `config.json`
- `requirements.txt`
- `start_bot.sh`
- `stop_bot.sh`
- `restart_bot.sh`
- `view_log.sh`

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 设置脚本权限

```bash
chmod +x start_bot.sh stop_bot.sh restart_bot.sh view_log.sh
```

### 4. 运行脚本

- 启动机器人：

  ```bash
  ./start_bot.sh
  ```

- 停止机器人：

  ```bash
  ./stop_bot.sh
  ```

- 重启机器人：

  ```bash
  ./restart_bot.sh
  ```

- 查看日志：
  ```bash
  ./view_log.sh
  ```

### 5. 设置开机自启（可选）

编辑 `/etc/rc.local` 文件，在 `exit 0` 之前添加：

```bash
cd /path/to/your/bot/directory
./start_bot.sh
```

## 使用说明

### 用户命令

- `/start` - 开始使用机器人
- `/help` - 显示帮助信息

### 反馈格式

- 使用 `#反馈` 开头发送一般反馈
- 使用 `#求片` 开头请求影视资源

### 管理员命令

- `/stats` - 查看反馈统计
- `/pending` - 查看待处理的反馈
- `/toggle_movie yes/no` - 开启/关闭求片功能

## 注意事项

1. 确保服务器有足够的磁盘空间存储日志文件
2. 定期检查日志文件大小，必要时进行清理
3. 建议使用虚拟环境运行机器人
4. 确保配置文件中的敏感信息已正确设置
