@echo off
chcp 65001 >nul
title Trip Agent
cd /d "%~dp0"

echo ========================================
echo   Trip Agent - Запуск...
echo ========================================
echo.

:: Проверяем наличие venv
if not exist "venv\Scripts\activate.bat" (
    echo Создаю виртуальное окружение...
    python -m venv venv
    if errorlevel 1 (
        echo Ошибка: Python не найден!
        echo Установите Python с https://python.org
        pause
        exit /b 1
    )
)

:: Активируем окружение
call venv\Scripts\activate.bat

:: Проверяем зависимости
python -c "import crewai" 2>nul
if errorlevel 1 (
    echo Устанавливаю зависимости...
    pip install -r requirements.txt
    playwright install chromium
)

:: Запускаем агента
echo.
echo Запуск агента...
echo.
python main.py

echo.
pause