# скрипт для работы с файлами проекта игнорируем venv и файлы кеша
import os
import sys

def scan_and_save(root_dir, output_file="files_content.txt"):
    """
    Сканирует директорию и сохраняет результаты в файл
    """
    # Получаем абсолютные пути для исключения
    script_path = os.path.abspath(__file__)
    output_path = os.path.abspath(output_file)
    
    with open(output_file, 'w', encoding='utf-8') as output:
        file_count = 0
        
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Исключаем папку __pycache__ из дальнейшего обхода
            if '__pycache__' in dirnames:
                dirnames.remove('__pycache__')
            if 'venv' in dirnames:
                dirnames.remove('venv')
            if 'frontend' in dirnames:
                dirnames.remove('frontend')
            if 'удалить' in dirnames:
                dirnames.remove('удалить')
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                abs_file_path = os.path.abspath(file_path)
                
                #-------BLACK-LIST_NAME----------
                # Пропускаем сам скрипт и выходной файл (по абсолютным путям)
                if abs_file_path == script_path or abs_file_path == output_path:
                    continue
                
                # Пропускаем файлы .pyc и файлы в папке __pycache__
                if filename.endswith('.pyc') or '__pycache__' in file_path.split(os.sep):
                    continue
                #---------------------------
                output.write(f"Файл: {file_path}\n")
                output.write("Содержимое:\n")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                        output.write(content)
                except UnicodeDecodeError:
                    try:
                        with open(file_path, 'r', encoding='cp1251') as file:
                            content = file.read()
                            output.write(content)
                    except:
                        output.write("[Файл содержит бинарные данные или неизвестную кодировку]")
                except Exception as e:
                    output.write(f"[Ошибка чтения файла: {str(e)}]")
                
                output.write("\n" * 2)  # Две пустые строки между файлами
                file_count += 1
        
        output.write(f"\nВсего обработано файлов: {file_count}")
    
    print(f"Результаты сохранены в файл: {output_file}")
    print(f"Обработано файлов: {file_count}")

def main():
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = os.getcwd()
    
    if not os.path.exists(directory):
        print(f"Директория '{directory}' не существует!")
        return
    
    if not os.path.isdir(directory):
        print(f"'{directory}' не является директорией!")
        return
    
    print(f"Сканирую директорию: {directory}")
    
    # Создаем имя для выходного файла на основе имени папки
    dir_name = os.path.basename(directory) or "root"
    output_file = f"files_content_{dir_name}.txt"
    
    scan_and_save(directory, output_file)

if __name__ == "__main__":
    main()