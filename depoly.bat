@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo 注意此脚本会清理并重新部署
echo.

docker --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未安装或未运行
    echo 请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker Compose 未安装
    pause
    exit /b 1
)

echo [OK] Docker 和 Docker Compose 已安装
echo.

REM 检查Protobuf文件
echo 检查Protobuf依赖...
if not exist "scraper\bilibili" (
    echo.
    echo [警告] 未找到 scraper\bilibili 目录
    echo 请确保已放置Bilibili的protobuf定义文件到 scraper\bilibili\ 目录
    echo.
    set /p continue="是否继续部署?(Y/N): "
    if /i not "!continue!"=="Y" (
        exit /b 0
    )
)

echo.
echo 停止并删除容器...
docker-compose down
echo.

echo 删除相关镜像...
docker rmi bilibili-comment-platform-scraper 2>nul
docker rmi bilibili-comment-platform-backend 2>nul
docker rmi bilibili-comment-platform-frontend 2>nul
docker rmi bilibili-comment-platform-admin 2>nul
docker rmi bilibili-comment-platform-nginx 2>nul
echo.

echo 重新构建镜像...
docker-compose build --no-cache
if errorlevel 1 (
    echo [错误] 镜像构建失败
    pause
    goto END
)

echo.
echo 启动服务...
docker-compose up -d
if errorlevel 1 (
    echo [错误] 服务启动失败
    pause
    goto END
)

echo [OK] 重新部署完成
echo.
timeout /t 15 /nobreak >nul
goto HEALTH

:HEALTH
echo.
echo [健康检查]
echo.
echo 检查后端服务...
curl -s http://localhost/api/health >nul 2>&1
if errorlevel 1 (
    echo [×] 后端服务未就绪
) else (
    echo [√] 后端服务正常
)

echo 检查爬虫服务...
curl -s http://localhost/scraper/health >nul 2>&1
if errorlevel 1 (
    echo [×] 爬虫服务未就绪
) else (
    echo [√] 爬虫服务正常
)

echo.
echo 服务访问地址:
echo.
echo   用户前端:      http://localhost
echo   管理后台:      http://localhost/admin
echo.
pause
goto END

:END
exit /b 0