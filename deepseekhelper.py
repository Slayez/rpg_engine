#!/usr/bin/env python3
"""
Скрипт для объединения содержимого всех файлов проекта в один общий файл.
Учитывает .gitignore и ограничение по расширениям.
Позволяет обойти ограничение на количество файлов при вложении (например, в контекст LLM).
Добавляет текстовое древо файлов в начало выходного файла.
"""

import os
import fnmatch
import sys
from pathlib import Path

# Конфигурация
OUTPUT_FILE = "combined_output.txt"          # Имя выходного файла
ALLOWED_EXTENSIONS = {".py", ".css", ".j2", ".js", ".html", ".txt"}  # Обрабатываемые расширения

def parse_gitignore(root_dir):
    """
    Читает .gitignore из корневой директории и возвращает список паттернов для игнорирования.
    Паттерны обрабатываются как правила для fnmatch.
    """
    gitignore_path = os.path.join(root_dir, ".gitignore")
    patterns = []
    if not os.path.isfile(gitignore_path):
        return patterns

    with open(gitignore_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Пропускаем пустые строки и комментарии
            if not line or line.startswith("#"):
                continue
            # Убираем завершающий слэш для единообразия (но в fnmatch он не нужен)
            if line.endswith("/"):
                line = line[:-1]
            patterns.append(line)
    return patterns

def is_ignored(path, patterns, root_dir):
    """
    Проверяет, должен ли путь (файл или директория) быть проигнорирован на основе паттернов .gitignore.
    Используется fnmatch для сопоставления с относительным путём.
    """
    # Получаем относительный путь от корня проекта
    rel_path = os.path.relpath(path, root_dir)
    # Для Unix-совместимых шаблонов заменяем разделители на '/'
    rel_path_unix = rel_path.replace(os.sep, "/")

    for pattern in patterns:
        # Обработка паттернов вида **/something (пока упрощённо)
        # Для простоты поддерживаем базовые wildcard * и ?, а также
        # неявное игнорирование файлов в любой поддиректории, если паттерн содержит '/'
        if fnmatch.fnmatch(rel_path_unix, pattern) or fnmatch.fnmatch(rel_path_unix, f"*/{pattern}"):
            return True
        # Также проверяем, не является ли текущий путь директорией, совпадающей с паттерном
        # (для предотвращения захода в игнорируемые директории)
        if os.path.isdir(path) and fnmatch.fnmatch(rel_path_unix, f"{pattern}/*"):
            return True
    return False

def get_allowed_files(root_dir, patterns, output_path, script_path):
    """
    Рекурсивно обходит root_dir и возвращает список файлов с допустимыми расширениями,
    исключая игнорируемые, а также выходной файл и сам скрипт.
    """
    allowed_files = []
    # Нормализуем абсолютные пути для корректного сравнения (даже если файлы ещё не существуют)
    abs_output = os.path.abspath(output_path)
    abs_script = os.path.abspath(script_path)

    for current_dir, dirs, files in os.walk(root_dir, topdown=True):
        # Удаляем из dirs те директории, которые подпадают под игнорирование
        dirs_to_remove = []
        for d in dirs:
            dir_full_path = os.path.join(current_dir, d)
            if is_ignored(dir_full_path, patterns, root_dir):
                dirs_to_remove.append(d)
        for d in dirs_to_remove:
            dirs.remove(d)

        for file in files:
            file_path = os.path.join(current_dir, file)
            abs_file = os.path.abspath(file_path)

            # Проверяем, не является ли файл выходным или текущим скриптом
            if abs_file == abs_output or abs_file == abs_script:
                continue

            # Проверка расширения
            ext = os.path.splitext(file)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue

            # Проверка игнорирования
            if is_ignored(file_path, patterns, root_dir):
                continue

            allowed_files.append(file_path)
    return allowed_files

def generate_file_tree(files, root_dir):
    """
    Создаёт текстовое представление дерева файлов, которые будут включены в результат.
    Возвращает строку с отформатированным деревом.
    """
    if not files:
        return " (нет файлов)\n"

    # Строим дерево в виде словаря: ключ – имя, значение – вложенный словарь (для папок) или None (для файлов)
    tree = {}
    for f in files:
        rel = os.path.relpath(f, root_dir)
        parts = rel.split(os.sep)
        node = tree
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            node = node[part]
        # Файл – лист
        node[parts[-1]] = None

    # Рекурсивная функция для вывода дерева
    def render_tree(node, prefix, is_last, name):
        lines = []
        # Текущий узел
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{name}")

        if isinstance(node, dict) and node:
            # Это директория с содержимым
            items = sorted(node.items(), key=lambda x: (isinstance(x[1], dict), x[0]))
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, (child_name, child_node) in enumerate(items):
                child_is_last = (i == len(items) - 1)
                lines.extend(render_tree(child_node, child_prefix, child_is_last, child_name))
        return lines

    # Собираем всё
    root_items = sorted(tree.items(), key=lambda x: (isinstance(x[1], dict), x[0]))
    all_lines = ["."]
    for i, (name, node) in enumerate(root_items):
        is_last = (i == len(root_items) - 1)
        all_lines.extend(render_tree(node, "", is_last, name))
    return "\n".join(all_lines) + "\n"

def combine_files(files, root_dir, output_path, tree_str):
    """
    Объединяет содержимое файлов в output_path.
    Каждый файл предваряется строкой с относительным путём.
    В начало записывается текстовое дерево файлов.
    """
    with open(output_path, "w", encoding="utf-8") as out_f:
        # Записываем дерево
        out_f.write("Древо включённых файлов:\n")
        out_f.write(tree_str)
        out_f.write("\n")  # отделяем от содержимого

        for file_path in files:
            # Относительный путь для отображения в выводе
            rel_path = os.path.relpath(file_path, root_dir)
            out_f.write(f"##### {rel_path} #####\n")
            try:
                with open(file_path, "r", encoding="utf-8") as in_f:
                    content = in_f.read()
                    out_f.write(content)
                    # Добавляем пустую строку между файлами, если содержимое не заканчивается переносом
                    if not content.endswith("\n"):
                        out_f.write("\n")
                    out_f.write("\n")  # разделитель между файлами
            except Exception as e:
                out_f.write(f"Ошибка чтения файла: {e}\n\n")

def main():
    root_dir = os.getcwd()                     # Корень проекта — текущая рабочая директория
    script_path = os.path.abspath(sys.argv[0]) # Путь к текущему скрипту
    output_path = os.path.join(root_dir, OUTPUT_FILE)

    # Предотвращаем случайную запись в существующий выходной файл (если он уже есть)
    if os.path.exists(output_path):
        print(f"Внимание: файл '{OUTPUT_FILE}' уже существует, он будет перезаписан.")

    # Чтение .gitignore
    patterns = parse_gitignore(root_dir)
    if patterns:
        print(f"Загружено {len(patterns)} правил из .gitignore")
    else:
        print(".gitignore не найден или пуст, все файлы будут рассмотрены (кроме текущего скрипта и выходного файла)")

    # Сбор всех подходящих файлов
    print("Сбор файлов...")
    files = get_allowed_files(root_dir, patterns, output_path, script_path)
    print(f"Найдено {len(files)} файлов для обработки")

    if not files:
        print("Нет файлов для объединения. Завершение.")
        return

    # Генерация дерева файлов
    print("Построение дерева...")
    tree_str = generate_file_tree(files, root_dir)

    # Объединение
    print(f"Запись в {OUTPUT_FILE}...")
    combine_files(files, root_dir, output_path, tree_str)
    print(f"Готово! Файл сохранён: {output_path}")

if __name__ == "__main__":
    main()