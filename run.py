#!/usr/bin/env python3
"""
Одновременный запуск бэкенда (FastAPI) и фронтенда (React).
Порты берутся из .env (BACKEND_PORT / FRONTEND_PORT).
"""

import os
import sys
import subprocess
import time
import platform
from dotenv import load_dotenv   # добавьте импорт

load_dotenv()                     # загружаем .env

def check_command(cmd, name):
    shell = platform.system() == "Windows"
    try:
        subprocess.run([cmd, "--version"], check=True, capture_output=True, shell=shell)
        return True
    except Exception:
        print(f"❌ {name} не найден. Установите и добавьте в PATH.")
        return False

def main():
    print(">>> Narrative Engine — запуск серверов <<<\n")
    if not check_command("node", "Node.js") or not check_command("npm", "npm"):
        sys.exit(1)

    backend_dir = os.path.join(os.getcwd(), "backend")
    frontend_dir = os.path.join(os.getcwd(), "frontend")
    if not os.path.isdir(backend_dir) or not os.path.isdir(frontend_dir):
        print("Ошибка: папки backend/frontend не найдены.")
        sys.exit(1)

    # ---------- читаем порты из .env ----------
    backend_port = os.getenv("BACKEND_PORT", "8000")
    frontend_port = os.getenv("FRONTEND_PORT", "3000")

    env = os.environ.copy()
    env["PYTHONPATH"] = backend_dir
    # передаём порт бэкенда в переменную для фронтенда, чтобы setupProxy знал
    env["BACKEND_PORT"] = backend_port

    # Бэкенд
    print(f"[1/2] Запуск бэкенда на порту {backend_port}...")
    backend_cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--reload", "--host", "0.0.0.0", "--port", backend_port
    ]
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=backend_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    time.sleep(3)
    if backend_proc.poll() is not None:
        output, _ = backend_proc.communicate()
        print("❌ Бэкенд завершился с ошибкой:")
        print(output)
        sys.exit(1)

    print(f"   Бэкенд PID {backend_proc.pid} (http://localhost:{backend_port})")

    # Фронтенд
    print(f"[2/2] Запуск фронтенда на порту {frontend_port}...")
    if not os.path.isdir(os.path.join(frontend_dir, "node_modules")):
        print("   Установка npm-зависимостей...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, shell=(platform.system() == "Windows"))

    # Устанавливаем PORT для react-scripts
    frontend_env = env.copy()
    frontend_env["PORT"] = frontend_port
    # также передаём порт бэкенда, чтобы setupProxy мог его использовать
    frontend_env["REACT_APP_API_URL"] = f"http://localhost:{backend_port}"

    frontend_shell = platform.system() == "Windows"
    frontend_cmd = ["cmd", "/c", "npm start"] if frontend_shell else ["npm", "start"]
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_dir,
        env=frontend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=frontend_shell
    )

    time.sleep(5)
    if frontend_proc.poll() is not None:
        output, _ = frontend_proc.communicate()
        print("❌ Фронтенд завершился с ошибкой:")
        print(output)
        backend_proc.terminate()
        sys.exit(1)

    print(f"   Фронтенд PID {frontend_proc.pid} (http://localhost:{frontend_port})")
    print("\n--- Серверы работают. Нажмите Ctrl+C для остановки ---\n")

    import threading
    def reader(proc, prefix):
        for line in proc.stdout:
            print(f"{prefix} {line.rstrip()}")

    threading.Thread(target=reader, args=(backend_proc, "[backend]"), daemon=True).start()
    threading.Thread(target=reader, args=(frontend_proc, "[frontend]"), daemon=True).start()

    try:
        while True:
            time.sleep(0.5)
            if backend_proc.poll() is not None:
                print("Бэкенд остановился. Завершение фронтенда...")
                frontend_proc.terminate()
                break
            if frontend_proc.poll() is not None:
                print("Фронтенд остановился. Завершение бэкенда...")
                backend_proc.terminate()
                break
    except KeyboardInterrupt:
        print("\nЗавершаю работу...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()
        time.sleep(1)
        backend_proc.kill()
        frontend_proc.kill()
        print("Серверы остановлены.")

if __name__ == "__main__":
    main()