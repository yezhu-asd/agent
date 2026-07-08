@echo off
REM Milvus Start Script (Windows)
REM ========================================
echo ========================================
echo  Campus Medical - Milvus Startup Script
echo ========================================
echo. 

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not found or not running
    echo Please install and start Docker Desktop first
    pause
    exit /b 1
)

echo [1/4] Check embedding data...
if not exist "embedding\embedding_merged\embeddings.npy" (
    echo [WARNING] embedding data file not found
    echo Please make sure data exists in embedding\embedding_merged\
) else (
    echo [OK] embedding data file found
)

echo.
echo [2/4] Start Milvus services...
docker-compose -f milvus/docker-compose.milvus.yml up -d

echo.
echo [3/4] Wait 30 seconds for Milvus to start...
timeout /t 30 /nobreak

echo.
echo [4/4] Milvus service status:
docker-compose -f milvus/docker-compose.milvus.yml ps

echo.
echo ========================================
echo           Done!
echo ========================================
echo.
echo Attu (Web UI): http://localhost:8080
echo Milvus Port: 19530
echo.
echo Next steps:
echo 1. Copy .env.example to .env
echo 2. Confirm VECTOR_DB_TYPE=milvus in .env
echo 3. Run: cd embedding ^&^& python upload_to_milvus.py
echo 4. Start app: python -m uvicorn app:app --reload
echo.
echo Detailed documentation: milvus\MILVUS_DEPLOYMENT.md
echo.
pause