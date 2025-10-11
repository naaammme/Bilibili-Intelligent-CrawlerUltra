<div align="center">
  <img src="/images/logo.svg" alt="BICU Logo" width="400">
  <h1>Bilibili Intelligent CrawlerUltra</h1>
  <blockquote>bilibili用户评论爬取和查询系统,支持docker一键部署和运行</blockquote>
</div>

---
## 介绍:
- Bicu是模仿aicu.cc写的b站用户评论爬取和查询系统
- 支持爬取视频,动态的全部评论,并自动保存进clickhouse
- 支持根据用户uid搜索历史名称和历史评论
## 免责声明:

- 本项目仅用于技术学习和研究
- 请勿用于商业用途或修改程序进行大规模爬取
- 使用本项目产生的任何后果由使用者自行承担
- 作者不对任何滥用行为负责

## 截图:
<div align="center">
  <img src="/images/1.png" alt="主页">
</div>

<div align="center">
  <img src="/images/2.png" alt="评论页面">
</div>

## 快速开始:

### 1. 环境要求
Windows:
- 安装Docker Desktop for Windows
- 在windows功能中打开虚拟机平台和适用于Linux的Windows子系统(WSL2)
- 在微软商店搜索Ubuntu并安装

MacOS:
- 安装Docker Desktop for Mac

Linux:
- 安装Docker Engine
### 2. 配置环境变量

编辑 `.env` 文件,根据需要修改配置:

```bash
# - CLICKHOUSE_PASSWORD: ClickHouse密码
# - BATCH_SIZE: 批量插入大小(默认:50000)
# - DEFAULT_MIN_DELAY/DEFAULT_MAX_DELAY: 爬虫延迟(默认:1.0-3.0秒)
```

### 3. 启动所有服务

**Windows:**
```bash
# 直接运行

deploy.bat
```

**Linux/Mac:**
```bash
docker-compose up -d
```

所有服务应该显示为 `Up` 状态。


##  使用说明

### 爬虫管理

1. 访问管理后台: http://localhost/admin
2. 设置延迟参数(推荐 1-3 秒)
3. 在"任务管理"中输入要爬取的内容,每行一个:
   ```
    364536139
    363901944
    1097897901199196164
    BVXXXXXXX
   ```
4. 点击"开始爬取"按钮
5. 在"爬虫日志"中查看实时进度
6. 在"数据统计"标签页查看数据库统计

### 支持的输入格式

- **BV号**: `BV1xx4y1x7xx` (视频)
- **av号**: `av123456` (视频)
- **动态ID(长)**: `1071500774534545411` (动态,>15位数字)
- **动态ID(短)**: `123456` (动态,普通数字)

### 用户查询

1. 访问前端: http://localhost
2. 输入用户 UID
3. 点击查询按钮
4. 查看用户基本信息和历史评论




