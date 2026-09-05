## Конфигурация

После инициализации (`infra-init`) создаётся файл `.infra.env` со всеми настройками.  
Вы можете переопределить имя файла через переменную окружения `INFRA_ENV_FILE`.

В `.infra.env` можно:
- Указать строки подключения к БД.
- Добавить произвольные каналы в переменную `CHANNELS` (через запятую) и задать для них параметры с префиксом `ИМЯ_КАНАЛА_`.
- Настроить пулы, таймауты, кеш и повторные попытки.

Пример добавления канала `report`:
```env
CHANNELS=read,write,admin,report
REPORT_POOL_SIZE=5
REPORT_MAX_OVERFLOW=2
REPORT_QUEUE_MAXSIZE=100
Затем используйте его в коде:

python
result = await router.read("user", 1, channel="report")
text

---

## 6. Команды для применения изменений

После того как вы замените файлы в своём репозитории:

```bash
git add infrastructure/templates/env_template.txt
git add infrastructure/templates/run_infrastructure_template.py
git add infrastructure/cli.py
git add README.md
git commit -m "feat: flexible config via .infra.env, arbitrary channels support"
git push
Затем клиент обновляет пакет и пересоздаёт конфигурацию:

bash
pip install --upgrade git+https://github.com/senia-glitch/event-infra.git
infra-init --force   # создаст .infra.env с новым содержимым
