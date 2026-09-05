event-infra
Инфраструктурный слой для проектов на PostgreSQL + SQLModel.
Поставляется как устанавливаемый Python-пакет. Обеспечивает миграции, асинхронный доступ к БД с пулами соединений, очередями задач, универсальным CRUD, кешированием и мониторингом. Не требует веб-сервера — запускается как отдельный процесс.

🚀 Возможности
Миграции – автоматическое сравнение SQLModel-моделей с БД и применение изменений (на основе Alembic).

Асинхронная инфраструктура – пулы соединений (asyncpg), очереди задач, диспетчеры с несколькими воркерами на канал.

Универсальный CRUD – создание, чтение, обновление, удаление записей на основе зарегистрированных моделей.

Произвольные SQL-запросы – выполнение кастомных запросов с параметрами через любой канал.

Гибкая конфигурация – все настройки в одном файле .infra.env (или любом другом, задаваемом через INFRA_ENV_FILE). Поддержка произвольного количества каналов.

Кеширование – in-memory кеш для операций чтения с настраиваемым TTL и размером.

Повторные попытки (retry) – автоматические ретраи при ошибках соединения, дедлоке, таймауте с экспоненциальной задержкой.

Мониторинг в реальном времени – отдельная команда infra-monitor для просмотра статистики по каналам, количеству обработанных задач, ошибкам и среднему времени выполнения.

Graceful shutdown – корректное завершение всех воркеров и закрытие пулов при остановке.

Полный сброс – команда infra-reset очищает БД и удаляет все файлы миграций, позволяя начать с нуля.

🎯 Преимущества
Автономность – не зависит от веб-фреймворка, может использоваться в любом Python-проекте.

Единый источник истины – схемы БД описываются через SQLModel в одном файле models.py.

Гибкость – легко добавлять новые каналы, менять размеры пулов, таймауты, настройки кеша и ретраев.

Простота – установка одной командой, инициализация за секунду, интуитивные команды.

Надёжность – пулы с проверкой соединений, автоматические переподключения, graceful shutdown.

📦 Установка
Установите пакет из GitHub:

bash
pip install git+https://github.com/senia-glitch/event-infra.git
Все зависимости (SQLAlchemy, SQLModel, Alembic, asyncpg, psycopg2-binary, httpx) установятся автоматически.

🏗️ Инициализация проекта
Перейдите в корневую папку вашего будущего проекта и выполните:

bash
infra-init
Будут созданы:

models.py – шаблон SQLModel-моделей (источник истины для схемы БД).

run_infrastructure.py – скрипт запуска инфраструктуры (миграции + EventRouter + метрики).

.infra.env – файл конфигурации со всеми параметрами и русскими комментариями.

alembic/ – папка для миграций (содержит env.py, script.py.mako, versions/).

Если нужно пересоздать файлы (например, после обновления пакета), используйте флаг --force:

bash
infra-init --force
⚙️ Конфигурация
Все настройки хранятся в файле .infra.env (по умолчанию).
Вы можете указать другой файл через переменную окружения INFRA_ENV_FILE:

bash
export INFRA_ENV_FILE=myconfig.env
python run_infrastructure.py
Основные параметры (подробно описаны в самом файле):

Подключение к БД – DB_URL (синхронный, для миграций), DB_URL_ASYNC (асинхронный, для работы).

Каналы – список имён через запятую в CHANNELS. Для каждого канала можно задать {NAME}_POOL_SIZE, {NAME}_MAX_OVERFLOW, {NAME}_QUEUE_MAXSIZE.

Общие настройки пулов – POOL_RECYCLE, POOL_PRE_PING, POOL_TIMEOUT.

Таймауты – DEFAULT_TIMEOUT, SHUTDOWN_TIMEOUT, MAX_CONCURRENCY.

Повторные попытки – RETRY_MAX_RETRIES, RETRY_DELAY_SECONDS, RETRY_BACKOFF_MULTIPLIER.

Кеш – CACHE_ENABLED, CACHE_TTL_SECONDS, CACHE_MAX_SIZE.

Пример добавления произвольного канала
Допустим, вам нужен канал report для отчётных запросов.
В .infra.env добавьте:

env
CHANNELS=read,write,admin,report
REPORT_POOL_SIZE=5
REPORT_MAX_OVERFLOW=2
REPORT_QUEUE_MAXSIZE=100
После запуска вы сможете использовать его в методах router.read(..., channel="report") или router.execute("report", "SELECT ...").

🏃 Запуск инфраструктуры
bash
python run_infrastructure.py
Что произойдёт:

Проверка и применение миграций (если модели изменились относительно БД).

Создание EventRouter с параметрами из .infra.env.

Запуск цикла вывода метрик (обновление каждую секунду).

Остановка – Ctrl+C. Произойдёт graceful shutdown.

🧰 Команды
Пакет предоставляет три консольные команды:

infra-init
Инициализирует проект в текущей директории.
Создаёт models.py, run_infrastructure.py, .infra.env и папку alembic.

bash
infra-init [--force]
infra-monitor
Запускает мониторинг инфраструктуры, подключаясь к запущенному сервису по адресу, указанному в переменной API_URL (по умолчанию http://localhost:8000).
Выводит статистику по каналам, обработанным задачам, ошибкам, среднему времени выполнения, а также метрики сценариев (если доступны).

bash
infra-monitor [интервал_в_секундах]
По умолчанию интервал 0.5 с. Остановка – Ctrl+C.

infra-reset
Полный сброс: удаляет все файлы миграций из папки alembic/versions/, очищает кеш модулей и удаляет все таблицы в публичной схеме указанной БД.

bash
infra-reset postgresql://user:pass@localhost:5432/dbname [--alembic-dir ./alembic]
Если папка alembic находится не в текущей директории, укажите её явно через --alembic-dir.

💻 Использование EventRouter
После создания роутера (router = await create_pipeline(...)) вы можете выполнять операции.

CRUD
python
# Создание
result = await router.create("user", {"name": "Alice", "email": "a@mail.com", "age": 25}, channel="write")
# Чтение
result = await router.read("user", 1, channel="read")
# Обновление
result = await router.update("user", 1, {"age": 26}, channel="write")
# Удаление
result = await router.delete("user", 1, channel="write")
Канал указывается явно. По умолчанию для create/update/delete используется write, для read – read.

Произвольный SQL
python
# Через канал read
result = await router.execute("read", "SELECT * FROM \"user\" WHERE age > :min", {"min": 18})
# Через канал report
result = await router.custom("SELECT COUNT(*) FROM orders", channel="report")
Повторные попытки (retry)
Глобальные настройки задаются в .infra.env.
При необходимости можно переопределить для конкретного вызова:

python
from infrastructure.event_infrastructure.config import RetryConfig

result = await router.read("user", 1, retry=RetryConfig(max_retries=5, delay_seconds=0.2))
Кеширование
Кеш работает для операций чтения. Включается/отключается в .infra.env.
Для конкретного вызова можно переопределить:

python
# Не использовать кеш для этого чтения
result = await router.read("user", 1, cache=False)
📊 Мониторинг
Встроенный мониторинг позволяет в реальном времени наблюдать за состоянием инфраструктуры.

Запуск – infra-monitor [interval].

Отображаемые данные:

Общее количество обработанных и упавших задач.

Размер очередей.

Количество активных воркеров и размер пула для каждого канала.

Среднее время выполнения задачи по каналам.

Информация о кеше.

Метрики сценариев (если реализованы в вашем приложении).

Мониторинг подключается к эндпоинтам /system/stats и /system/scenario-metrics вашего веб-сервера, поэтому его можно использовать как в локальной разработке, так и на удалённых серверах.

🧹 Сброс и очистка
Команда infra-reset выполняет полную очистку:

Удаляет все файлы миграций из alembic/versions/ (кроме __init__.py).

Удаляет папки __pycache__ внутри alembic.

Очищает кеш загруженных модулей Python.

Удаляет все таблицы в публичной схеме БД.

После сброса можно снова запустить run_infrastructure.py – миграции будут созданы заново, и БД будет построена с нуля.

Внимание: операция необратима! Убедитесь, что у вас есть бэкап данных, если они важны.

📁 Структура пакета
text
event-infra/
├── infrastructure/
│   ├── __init__.py
│   ├── cli.py                  # точки входа команд
│   ├── config_loader.py        # загрузка .env/.infra.env
│   ├── monitor.py              # мониторинг
│   ├── templates/              # шаблоны для infra-init
│   ├── db_migrator/            # утилита миграций
│   └── event_infrastructure/   # ядро (пулы, очереди, CRUD)
├── pyproject.toml
└── README.md
🔧 Требования
Python 3.8+

PostgreSQL (9.6+)

Установленный пакет (см. раздел «Установка»)

📝 Пример использования
1. Установка пакета

bash
pip install git+https://github.com/senia-glitch/event-infra.git
2. Инициализация

bash
mkdir my_project && cd my_project
infra-init
3. Настройка БД
Отредактировать .infra.env, указать свои DB_URL и DB_URL_ASYNC.

4. Запуск

bash
python run_infrastructure.py
5. Использование в коде (например, в другом модуле вашего приложения)

python
from infrastructure.event_infrastructure import create_pipeline
from models import get_all_schemas

router = await create_pipeline(
    db_url="postgresql+asyncpg://...",
    schemas=get_all_schemas(),
    # параметры из .infra.env автоматически подхватятся
)
user = await router.read("user", 42)
📄 Лицензия
MIT

🤝 Вклад и обратная связь
Если вы нашли баг или хотите предложить улучшение, создайте Issue или Pull Request в репозитории. Все идеи приветствуются!

Удачного использования! 🚀
