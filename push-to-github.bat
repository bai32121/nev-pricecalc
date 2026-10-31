@echo off
cd /d "%~dp0"

echo ==================================================
echo    新能源车价计算器  -  一键推送到 GitHub
echo ==================================================
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo [错误] 这台电脑上没找到 git 命令。
    echo 请先安装 Git for Windows: https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)

rem ---- 网络：国内直连 github.com 基本不通，自动找本机代理客户端 ----
set "PX="
netstat -an | findstr /c:"127.0.0.1:7890" >nul && set "PX=7890"
if not defined PX (
    netstat -an | findstr /c:"127.0.0.1:7897" >nul && set "PX=7897"
)
if not defined PX (
    netstat -an | findstr /c:"127.0.0.1:10809" >nul && set "PX=10809"
)
if not defined PX (
    netstat -an | findstr /c:"127.0.0.1:10808" >nul && set "PX=10808"
)
if defined PX (
    set "HTTPS_PROXY=http://127.0.0.1:%PX%"
    set "HTTP_PROXY=http://127.0.0.1:%PX%"
    echo [网络] 检测到本地代理端口 %PX%，已让 git 走代理
) else (
    echo [网络] 没检测到本地代理，将尝试直连 GitHub
    echo        如果报 SSL/TLS 或连接超时，先把代理软件打开再重试
)
echo.

rem ---- 看看是不是已经配过地址了 ----
set "EXISTING="
for /f "delims=" %%u in ('git config --get remote.origin.url 2^>nul') do set "EXISTING=%%u"

if defined EXISTING (
    echo 已经配好的地址: %EXISTING%
    echo 直接按回车就用这个，想换别的就粘贴新地址再回车。
) else (
    echo 请粘贴仓库地址。
    echo 在仓库页面点绿色 Code 按钮，选 HTTPS，复制那一整行都行，
    echo 形如 git remote add origin https://github.com/xxxx/yyyy.git
)
echo.

set "REPO="
set /p REPO=按回车确认，或粘贴新地址: 

if "%REPO%"=="" (
    if defined EXISTING (
        set "REPO=%EXISTING%"
        echo 使用已配置的地址。
    ) else (
        echo.
        echo [错误] 没输入地址，已取消。
        echo.
        pause
        exit /b 1
    )
)

rem ---- 容错：整行粘贴时，从中挑出以 http 开头的那一段 ----
set "REPO=%REPO:"=%"
set "URL="
for %%w in (%REPO%) do (
    echo %%w | findstr /b /i "https://" >nul && set "URL=%%w"
)
if not defined URL (
    for %%w in (%REPO%) do (
        echo %%w | findstr /b /i "http://" >nul && set "URL=%%w"
    )
)
if not defined URL set "URL=%REPO%"
set "REPO=%URL%"

echo.
echo 目标仓库: %REPO%
echo.
echo 开始推送。如果弹出 GitHub 登录窗口，在里面点用浏览器登录并授权。
echo 只此一次，以后就不用再登了。
echo.

git remote remove origin >nul 2>nul
git remote add origin "%REPO%"
if defined PX (
    git config http.proxy "http://127.0.0.1:%PX%"
    git config https.proxy "http://127.0.0.1:%PX%"
)

git push -u origin main
if errorlevel 1 goto fail

echo.
echo ==================================================
echo    推送成功
echo ==================================================
echo.
echo 下一步：
echo   1. 打开仓库网页，点顶部的 Actions 标签
echo   2. 会看到一个叫 Build unsigned IPA 的任务在跑
echo   3. 等大约 10 分钟，变成绿色对勾就好了
echo   4. 点左侧 Releases，下载里面那个 .ipa 文件
echo   5. 传到 iPhone，长按它，选用 TrollStore 打开
echo.
pause
exit /b 0

:fail
echo.
echo ==================================================
echo    推送失败
echo ==================================================
echo.
echo 请把上面这段红字或黄字整段复制发给助手，不要自己猜着改。
echo.
echo 几种常见情况：
echo   - SSL/TLS 或 connection reset : 代理没生效，检查代理软件是否开着
echo   - 一直停在原地不动 : 登录窗口在后台等你去点，看看任务栏
echo   - rejected 或 fetch first : 建仓库时勾了 README，需要先合并
echo.
pause
exit /b 1
